"""Service restart manager with exponential backoff and intelligent retry logic."""

import asyncio
from datetime import datetime
from uuid import UUID

import structlog

from ...domain.entities.service import Service
from ..dto.health_dto import RestartAttempt
from .service_manager import ServiceManager

logger = structlog.get_logger()


class RestartManager:
    """Manages service restarts with exponential backoff and retry limits."""

    def __init__(self, service_manager: ServiceManager):
        self._service_manager = service_manager
        self._restart_attempts: dict[UUID, list[RestartAttempt]] = {}
        self._restart_tasks: dict[UUID, asyncio.Task] = {}

    async def schedule_restart(
        self,
        service: Service,
        trigger_reason: str,
        restart_policy: dict | None = None
    ) -> bool:
        """Schedule a service restart with exponential backoff.

        Args:
            service: Service to restart
            trigger_reason: Reason for the restart (e.g., "health_check_failure")
            restart_policy: Optional restart policy override

        Returns:
            True if restart was scheduled, False if max attempts reached
        """
        # Get restart policy (from service config or defaults)
        policy = restart_policy or service.restart_policy or self._get_default_restart_policy()

        if not policy.get('enabled', True):
            logger.info("Restart disabled for service", service_name=service.name)
            return False

        # Check if we've exceeded max attempts
        attempts = self._restart_attempts.get(service.id, [])
        max_attempts = policy.get('max_attempts', 5)

        if len(attempts) >= max_attempts:
            logger.error("Maximum restart attempts reached",
                        service_name=service.name,
                        attempts=len(attempts),
                        max_attempts=max_attempts)
            return False

        # Cancel any existing restart task
        if service.id in self._restart_tasks:
            self._restart_tasks[service.id].cancel()

        # Calculate delay using exponential backoff
        delay = self._calculate_backoff_delay(attempts, policy)

        logger.info("Scheduling service restart",
                   service_name=service.name,
                   attempt_number=len(attempts) + 1,
                   delay_seconds=delay,
                   trigger_reason=trigger_reason)

        # Schedule the restart
        task = asyncio.create_task(
            self._execute_restart_with_delay(service, trigger_reason, delay, policy),
            name=f"restart_{service.name}_{len(attempts) + 1}"
        )
        self._restart_tasks[service.id] = task

        return True

    async def cancel_restart(self, service_id: UUID) -> bool:
        """Cancel a scheduled restart for a service.

        Args:
            service_id: ID of the service

        Returns:
            True if restart was cancelled, False if no restart was scheduled
        """
        if service_id in self._restart_tasks:
            task = self._restart_tasks[service_id]
            task.cancel()
            del self._restart_tasks[service_id]
            logger.info("Cancelled scheduled restart", service_id=str(service_id))
            return True
        return False

    def reset_restart_attempts(self, service_id: UUID) -> None:
        """Reset restart attempts for a service (e.g., after successful health check).

        Args:
            service_id: ID of the service
        """
        if service_id in self._restart_attempts:
            attempts_count = len(self._restart_attempts[service_id])
            del self._restart_attempts[service_id]
            logger.info("Reset restart attempts",
                       service_id=str(service_id),
                       previous_attempts=attempts_count)

    def get_restart_attempts(self, service_id: UUID) -> list[RestartAttempt]:
        """Get restart attempts for a service.

        Args:
            service_id: ID of the service

        Returns:
            List of restart attempts
        """
        return self._restart_attempts.get(service_id, []).copy()

    def get_restart_count(self, service_id: UUID) -> int:
        """Get the number of restart attempts for a service.

        Args:
            service_id: ID of the service

        Returns:
            Number of restart attempts
        """
        return len(self._restart_attempts.get(service_id, []))

    def is_restart_scheduled(self, service_id: UUID) -> bool:
        """Check if a restart is currently scheduled for a service.

        Args:
            service_id: ID of the service

        Returns:
            True if restart is scheduled
        """
        return service_id in self._restart_tasks

    async def _execute_restart_with_delay(
        self,
        service: Service,
        trigger_reason: str,
        delay: float,
        policy: dict
    ) -> None:
        """Execute a restart after the specified delay."""
        try:
            # Wait for the delay period
            if delay > 0:
                logger.info("Waiting before restart attempt",
                           service_name=service.name,
                           delay_seconds=delay)
                await asyncio.sleep(delay)

            # Execute the restart
            await self._execute_restart(service, trigger_reason, delay, policy)

        except asyncio.CancelledError:
            logger.info("Restart cancelled", service_name=service.name)
        except Exception as e:
            logger.exception("Error in restart execution",
                           service_name=service.name,
                           error=str(e))
        finally:
            # Clean up the task reference
            self._restart_tasks.pop(service.id, None)

    async def _execute_restart(
        self,
        service: Service,
        trigger_reason: str,
        delay: float,
        policy: dict
    ) -> None:
        """Execute the actual restart operation."""
        attempt_number = len(self._restart_attempts.get(service.id, [])) + 1
        restart_attempt = RestartAttempt(
            service_id=service.id,
            service_name=service.name,
            attempt_number=attempt_number,
            triggered_at=datetime.now(),
            trigger_reason=trigger_reason,
            success=False,
            delay_before_attempt=delay
        )

        try:
            logger.info("Executing service restart",
                       service_name=service.name,
                       attempt_number=attempt_number,
                       trigger_reason=trigger_reason)

            # Stop the service first
            stop_success = await self._service_manager.stop_service(service)
            if not stop_success:
                logger.warning("Failed to stop service before restart",
                             service_name=service.name)

            # Wait a moment for cleanup
            await asyncio.sleep(1)

            # Start the service
            start_result = await self._service_manager.start_service(service)

            if start_result.success:
                restart_attempt.success = True
                logger.info("Service restart successful",
                           service_name=service.name,
                           attempt_number=attempt_number)

                # Reset restart attempts on successful restart
                self.reset_restart_attempts(service.id)
            else:
                restart_attempt.error = start_result.error or "Unknown start error"
                logger.error("Service restart failed",
                           service_name=service.name,
                           attempt_number=attempt_number,
                           error=restart_attempt.error)

        except Exception as e:
            restart_attempt.error = str(e)
            logger.exception("Exception during service restart",
                           service_name=service.name,
                           attempt_number=attempt_number,
                           error=str(e))

        # Record the restart attempt
        if service.id not in self._restart_attempts:
            self._restart_attempts[service.id] = []
        self._restart_attempts[service.id].append(restart_attempt)

        # Log restart attempt details
        logger.info("Restart attempt completed",
                   service_name=service.name,
                   attempt_number=attempt_number,
                   success=restart_attempt.success,
                   total_attempts=len(self._restart_attempts[service.id]))

    def _calculate_backoff_delay(self, attempts: list[RestartAttempt], policy: dict) -> float:
        """Calculate the delay before the next restart attempt using exponential backoff.

        Args:
            attempts: Previous restart attempts
            policy: Restart policy configuration

        Returns:
            Delay in seconds
        """
        if not attempts:
            return 0.0  # No delay for first attempt

        attempt_number = len(attempts)
        initial_delay = policy.get('initial_delay', 1)  # seconds
        backoff_multiplier = policy.get('backoff_multiplier', 2.0)
        max_delay = policy.get('max_delay', 300)  # 5 minutes max

        # Calculate exponential backoff: initial_delay * (multiplier ^ (attempt - 1))
        delay = initial_delay * (backoff_multiplier ** (attempt_number - 1))

        # Cap at maximum delay
        delay = min(delay, max_delay)

        return delay

    def _get_default_restart_policy(self) -> dict:
        """Get the default restart policy."""
        return {
            'enabled': True,
            'max_attempts': 5,
            'initial_delay': 1,  # 1 second
            'backoff_multiplier': 2.0,
            'max_delay': 300  # 5 minutes
        }
