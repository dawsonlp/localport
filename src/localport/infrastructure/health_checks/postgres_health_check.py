"""PostgreSQL-specific health check implementation."""

import asyncio
from typing import Any

import structlog

logger = structlog.get_logger()


class PostgreSQLHealthCheck:
    """PostgreSQL-specific health check using database connectivity."""

    def __init__(self, timeout: float = 10.0):
        """Initialize PostgreSQL health check.
        
        Args:
            timeout: Connection timeout in seconds
        """
        self.timeout = timeout

    async def check(self, config: dict[str, Any]) -> bool:
        """Check PostgreSQL connectivity via database connection.
        
        Args:
            config: Configuration containing database connection parameters
            
        Returns:
            True if PostgreSQL is healthy, False otherwise
        """
        try:
            # Import psycopg here to make it optional
            try:
                import psycopg
                from psycopg import DatabaseError, OperationalError
            except ImportError:
                logger.error("psycopg not installed. Install with: pip install psycopg[binary]")
                return False

            # Build connection string
            connection_string = self._build_connection_string(config)

            # Test connection
            try:
                async with psycopg.AsyncConnection.connect(
                    connection_string,
                    connect_timeout=self.timeout
                ) as conn:
                    # Execute a simple query to verify the connection works
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT 1")
                        result = await cur.fetchone()

                        if result and result[0] == 1:
                            logger.debug("PostgreSQL health check passed",
                                        host=config.get('host', 'localhost'),
                                        database=config.get('database', 'postgres'))
                            return True
                        else:
                            logger.debug("PostgreSQL health check failed - unexpected query result")
                            return False

            except (OperationalError, DatabaseError) as e:
                logger.debug("PostgreSQL health check failed - database error",
                            host=config.get('host', 'localhost'),
                            database=config.get('database', 'postgres'),
                            error=str(e))
                return False

        except Exception as e:
            logger.debug("PostgreSQL health check failed - unexpected error",
                        host=config.get('host', 'localhost'),
                        database=config.get('database', 'postgres'),
                        error=str(e))
            return False

    def _build_connection_string(self, config: dict[str, Any]) -> str:
        """Build PostgreSQL connection string from configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            PostgreSQL connection string
        """
        # Extract connection parameters with defaults
        host = config.get('host', 'localhost')
        port = config.get('port', 5432)
        database = config.get('database', 'postgres')
        user = config.get('user', 'postgres')
        password = config.get('password', '')

        # Build connection string
        conn_parts = [
            f"host={host}",
            f"port={port}",
            f"dbname={database}",
            f"user={user}"
        ]

        if password:
            conn_parts.append(f"password={password}")

        # Add SSL configuration if specified
        sslmode = config.get('sslmode')
        if sslmode:
            conn_parts.append(f"sslmode={sslmode}")

        # Add connection timeout
        conn_parts.append(f"connect_timeout={int(self.timeout)}")

        return " ".join(conn_parts)

    async def check_database_exists(self, config: dict[str, Any], database_name: str) -> bool:
        """Check if a specific database exists.
        
        Args:
            config: Configuration containing connection parameters
            database_name: Name of the database to check
            
        Returns:
            True if database exists, False otherwise
        """
        try:
            import psycopg

            # Connect to the default postgres database to check for existence
            check_config = config.copy()
            check_config['database'] = 'postgres'  # Connect to default database

            connection_string = self._build_connection_string(check_config)

            async with psycopg.AsyncConnection.connect(
                connection_string,
                connect_timeout=self.timeout
            ) as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "SELECT 1 FROM pg_database WHERE datname = %s",
                        (database_name,)
                    )
                    result = await cur.fetchone()

                    exists = result is not None
                    logger.debug("PostgreSQL database existence check",
                                database=database_name,
                                exists=exists)
                    return exists

        except Exception as e:
            logger.debug("PostgreSQL database existence check failed",
                        database=database_name,
                        error=str(e))
            return False

    async def check_table_exists(self, config: dict[str, Any], table_name: str, schema: str = 'public') -> bool:
        """Check if a specific table exists.
        
        Args:
            config: Configuration containing connection parameters
            table_name: Name of the table to check
            schema: Schema name (default: 'public')
            
        Returns:
            True if table exists, False otherwise
        """
        try:
            import psycopg

            connection_string = self._build_connection_string(config)

            async with psycopg.AsyncConnection.connect(
                connection_string,
                connect_timeout=self.timeout
            ) as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_schema = %s AND table_name = %s
                        """,
                        (schema, table_name)
                    )
                    result = await cur.fetchone()

                    exists = result is not None
                    logger.debug("PostgreSQL table existence check",
                                table=f"{schema}.{table_name}",
                                exists=exists)
                    return exists

        except Exception as e:
            logger.debug("PostgreSQL table existence check failed",
                        table=f"{schema}.{table_name}",
                        error=str(e))
            return False

    async def check_user_permissions(self, config: dict[str, Any], required_permissions: list = None) -> bool:
        """Check if the user has required permissions.
        
        Args:
            config: Configuration containing connection parameters
            required_permissions: List of required permissions to check
            
        Returns:
            True if user has required permissions, False otherwise
        """
        if required_permissions is None:
            required_permissions = ['CONNECT']

        try:
            import psycopg

            connection_string = self._build_connection_string(config)
            user = config.get('user', 'postgres')
            database = config.get('database', 'postgres')

            async with psycopg.AsyncConnection.connect(
                connection_string,
                connect_timeout=self.timeout
            ) as conn:
                async with conn.cursor() as cur:
                    # Check database-level permissions
                    await cur.execute(
                        """
                        SELECT has_database_privilege(%s, %s, %s) as has_permission
                        """,
                        (user, database, 'CONNECT')
                    )
                    result = await cur.fetchone()

                    has_connect = result and result[0]

                    if not has_connect:
                        logger.debug("PostgreSQL user lacks CONNECT permission",
                                    user=user,
                                    database=database)
                        return False

                    # Check for additional permissions if specified
                    for permission in required_permissions:
                        if permission.upper() == 'CONNECT':
                            continue  # Already checked

                        # Check table-level permissions (simplified check)
                        if permission.upper() in ['SELECT', 'INSERT', 'UPDATE', 'DELETE']:
                            await cur.execute(
                                """
                                SELECT has_schema_privilege(%s, 'public', 'USAGE') as has_usage
                                """,
                                (user,)
                            )
                            result = await cur.fetchone()

                            if not (result and result[0]):
                                logger.debug("PostgreSQL user lacks schema permissions",
                                            user=user,
                                            permission=permission)
                                return False

                    logger.debug("PostgreSQL user permissions check passed",
                                user=user,
                                permissions=required_permissions)
                    return True

        except Exception as e:
            logger.debug("PostgreSQL user permissions check failed",
                        user=config.get('user', 'postgres'),
                        error=str(e))
            return False

    async def get_server_version(self, config: dict[str, Any]) -> str | None:
        """Get PostgreSQL server version.
        
        Args:
            config: Configuration containing connection parameters
            
        Returns:
            Server version string if successful, None otherwise
        """
        try:
            import psycopg

            connection_string = self._build_connection_string(config)

            async with psycopg.AsyncConnection.connect(
                connection_string,
                connect_timeout=self.timeout
            ) as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT version()")
                    result = await cur.fetchone()

                    if result:
                        version = result[0]
                        logger.debug("PostgreSQL server version retrieved",
                                    version=version)
                        return version

                    return None

        except Exception as e:
            logger.debug("PostgreSQL server version check failed",
                        error=str(e))
            return None

    async def check_connection_pool(self, config: dict[str, Any], pool_size: int = 5) -> bool:
        """Check if multiple connections can be established (connection pool test).
        
        Args:
            config: Configuration containing connection parameters
            pool_size: Number of concurrent connections to test
            
        Returns:
            True if all connections successful, False otherwise
        """
        try:
            import psycopg

            connection_string = self._build_connection_string(config)

            # Create multiple connections concurrently
            async def test_connection():
                async with psycopg.AsyncConnection.connect(
                    connection_string,
                    connect_timeout=self.timeout
                ) as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT 1")
                        result = await cur.fetchone()
                        return result and result[0] == 1

            # Test multiple connections
            tasks = [test_connection() for _ in range(pool_size)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check if all connections succeeded
            successful_connections = sum(1 for result in results if result is True)

            logger.debug("PostgreSQL connection pool test",
                        pool_size=pool_size,
                        successful=successful_connections,
                        all_successful=successful_connections == pool_size)

            return successful_connections == pool_size

        except Exception as e:
            logger.debug("PostgreSQL connection pool test failed",
                        pool_size=pool_size,
                        error=str(e))
            return False


# Convenience function for simple health checks
async def check_postgres_health(
    host: str = 'localhost',
    port: int = 5432,
    database: str = 'postgres',
    user: str = 'postgres',
    password: str = '',
    timeout: float = 10.0
) -> bool:
    """Simple PostgreSQL health check function.
    
    Args:
        host: Database host
        port: Database port
        database: Database name
        user: Database user
        password: Database password
        timeout: Connection timeout in seconds
        
    Returns:
        True if PostgreSQL is healthy, False otherwise
    """
    health_check = PostgreSQLHealthCheck(timeout=timeout)
    config = {
        'host': host,
        'port': port,
        'database': database,
        'user': user,
        'password': password
    }
    return await health_check.check(config)
