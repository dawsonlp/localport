"""Unit tests for KubectlAdapter."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio
import psutil

from src.localport.infrastructure.adapters.kubectl_adapter import KubectlAdapter
from src.localport.infrastructure.adapters.base_adapter import PortForwardingAdapter
from src.localport.domain.value_objects.connection_info import ConnectionInfo
from src.localport.domain.enums import ForwardingTechnology


class TestKubectlAdapter:
    """Test cases for KubectlAdapter."""

    def test_inheritance(self):
        """Test that KubectlAdapter properly inherits from PortForwardingAdapter."""
        adapter = KubectlAdapter()
        assert isinstance(adapter, PortForwardingAdapter)

    def test_get_adapter_name(self):
        """Test get_adapter_name method."""
        adapter = KubectlAdapter()
        assert adapter.get_adapter_name() == "Kubectl Port Forward"

    def test_get_required_tools(self):
        """Test get_required_tools method."""
        adapter = KubectlAdapter()
        assert adapter.get_required_tools() == ["kubectl"]

    @pytest.mark.asyncio
    async def test_validate_connection_info_valid(self):
        """Test validate_connection_info with valid configuration."""
        adapter = KubectlAdapter()
        connection_info = ConnectionInfo.kubectl(
            resource_name='my-service',
            namespace='default',
            resource_type='service'
        )
        
        with patch.object(adapter, 'list_contexts', return_value=[]):
            errors = await adapter.validate_connection_info(connection_info)
            assert errors == []

    @pytest.mark.asyncio
    async def test_validate_connection_info_missing_resource_name(self):
        """Test validate_connection_info with missing resource_name."""
        adapter = KubectlAdapter()
        # Test that ConnectionInfo validation catches empty resource_name at creation
        with pytest.raises(ValueError, match="resource_name cannot be empty"):
            ConnectionInfo(
                ForwardingTechnology.KUBECTL,
                {'resource_name': '', 'namespace': 'default'}
            )

    @pytest.mark.asyncio
    async def test_validate_connection_info_invalid_resource_type(self):
        """Test validate_connection_info with invalid resource_type."""
        adapter = KubectlAdapter()
        # Test that ConnectionInfo validation catches invalid resource_type at creation
        with pytest.raises(ValueError, match="resource_type.*invalid"):
            ConnectionInfo(
                ForwardingTechnology.KUBECTL,
                {
                    'resource_name': 'my-service',
                    'resource_type': 'invalid-type'
                }
            )

    @pytest.mark.asyncio
    async def test_validate_connection_info_invalid_context(self):
        """Test validate_connection_info with invalid context."""
        adapter = KubectlAdapter()
        connection_info = ConnectionInfo(
            ForwardingTechnology.KUBECTL,
            {
                'resource_name': 'my-service',
                'context': 'non-existent-context'
            }
        )
        
        with patch.object(adapter, 'list_contexts', return_value=['valid-context']):
            errors = await adapter.validate_connection_info(connection_info)
            assert any("context" in error and "not found" in error for error in errors)

    @pytest.mark.asyncio
    async def test_validate_connection_info_wrong_technology(self):
        """Test validate_connection_info with wrong technology."""
        adapter = KubectlAdapter()
        connection_info = ConnectionInfo.ssh(
            host='example.com',
            user='test'
        )
        
        errors = await adapter.validate_connection_info(connection_info)
        assert len(errors) == 1
        assert "not for kubectl technology" in errors[0]

    @pytest.mark.asyncio
    async def test_is_port_forward_running_delegates(self):
        """Test that is_port_forward_running delegates to is_process_running."""
        adapter = KubectlAdapter()
        
        with patch.object(adapter, 'is_process_running', return_value=True) as mock_method:
            result = await adapter.is_port_forward_running(12345)
            assert result is True
            mock_method.assert_called_once_with(12345)

    @pytest.mark.asyncio
    async def test_validate_kubectl_available_success(self):
        """Test validate_kubectl_available when kubectl is available."""
        adapter = KubectlAdapter()
        
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b'{"clientVersion": {}}', b'')
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            result = await adapter.validate_kubectl_available()
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_kubectl_available_failure(self):
        """Test validate_kubectl_available when kubectl is not available."""
        adapter = KubectlAdapter()
        
        with patch('asyncio.create_subprocess_exec', side_effect=FileNotFoundError()):
            result = await adapter.validate_kubectl_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_list_contexts_success(self):
        """Test list_contexts when kubectl returns contexts."""
        adapter = KubectlAdapter()
        
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b'context1\ncontext2\ncontext3\n', b'')
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            contexts = await adapter.list_contexts()
            assert contexts == ['context1', 'context2', 'context3']

    @pytest.mark.asyncio
    async def test_list_contexts_failure(self):
        """Test list_contexts when kubectl command fails."""
        adapter = KubectlAdapter()
        
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b'', b'error message')
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            contexts = await adapter.list_contexts()
            assert contexts == []

    @pytest.mark.asyncio
    async def test_validate_kubectl_connectivity_success(self):
        """Test validate_kubectl_connectivity with successful connection."""
        adapter = KubectlAdapter()
        connection_info = ConnectionInfo.kubectl(
            resource_name='my-service',
            namespace='default'
        )
        
        mock_process = AsyncMock()
        mock_process.returncode = 0
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch('asyncio.wait_for', return_value=None):
                success, message = await adapter.validate_kubectl_connectivity(connection_info)
                assert success is True
                assert "connectivity verified" in message

    @pytest.mark.asyncio
    async def test_validate_kubectl_connectivity_failure(self):
        """Test validate_kubectl_connectivity with failed connection."""
        adapter = KubectlAdapter()
        connection_info = ConnectionInfo.kubectl(
            resource_name='my-service',
            namespace='default'
        )
        
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b'connection refused')
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch('asyncio.wait_for', return_value=None):
                success, message = await adapter.validate_kubectl_connectivity(connection_info)
                assert success is False
                assert "connection failed" in message

    @pytest.mark.asyncio
    async def test_validate_resource_exists_success(self):
        """Test validate_resource_exists with existing resource."""
        adapter = KubectlAdapter()
        connection_info = ConnectionInfo.kubectl(
            resource_name='my-service',
            namespace='default',
            resource_type='service'
        )
        
        mock_process = MagicMock()
        mock_process.returncode = 0
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch('asyncio.wait_for', return_value=None):
                success, message = await adapter.validate_resource_exists(connection_info)
                assert success is True
                assert "found" in message

    @pytest.mark.asyncio
    async def test_validate_resource_exists_failure(self):
        """Test validate_resource_exists with non-existing resource."""
        adapter = KubectlAdapter()
        connection_info = ConnectionInfo.kubectl(
            resource_name='non-existent',
            namespace='default',
            resource_type='service'
        )
        
        mock_process = MagicMock()
        mock_process.returncode = 1
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            with patch('asyncio.wait_for', return_value=None):
                success, message = await adapter.validate_resource_exists(connection_info)
                assert success is False
                assert "not found" in message

    @pytest.mark.asyncio
    async def test_validate_dependencies_success(self):
        """Test validate_dependencies when all dependencies are available."""
        adapter = KubectlAdapter()
        
        with patch.object(adapter, 'validate_kubectl_available', return_value=True):
            all_available, missing_tools = await adapter.validate_dependencies()
            assert all_available is True
            assert missing_tools == []

    @pytest.mark.asyncio
    async def test_validate_dependencies_failure(self):
        """Test validate_dependencies when dependencies are missing."""
        adapter = KubectlAdapter()
        
        with patch.object(adapter, 'validate_kubectl_available', return_value=False):
            all_available, missing_tools = await adapter.validate_dependencies()
            assert all_available is False
            assert len(missing_tools) == 1
            assert "kubectl" in missing_tools[0]

    @pytest.mark.asyncio
    async def test_check_prerequisites_success(self):
        """Test check_prerequisites when all prerequisites are met."""
        adapter = KubectlAdapter()
        
        with patch.object(adapter, 'validate_dependencies', return_value=(True, [])):
            result = await adapter.check_prerequisites()
            assert result is True

    @pytest.mark.asyncio
    async def test_check_prerequisites_failure(self):
        """Test check_prerequisites when prerequisites are not met."""
        adapter = KubectlAdapter()
        
        with patch.object(adapter, 'validate_dependencies', return_value=(False, ['kubectl'])):
            result = await adapter.check_prerequisites()
            assert result is False

    def test_interface_compliance(self):
        """Test that KubectlAdapter properly implements PortForwardingAdapter."""
        import inspect
        
        adapter = KubectlAdapter()
        assert isinstance(adapter, PortForwardingAdapter)
        
        # Check all abstract methods are implemented
        abstract_methods = []
        for name, method in inspect.getmembers(PortForwardingAdapter, predicate=inspect.isfunction):
            if getattr(method, '__isabstractmethod__', False):
                abstract_methods.append(name)
        
        for method_name in abstract_methods:
            assert hasattr(adapter, method_name), f"Missing method: {method_name}"
            method = getattr(adapter, method_name)
            assert callable(method), f"Method {method_name} is not callable"

    @pytest.mark.asyncio
    async def test_start_port_forward_success(self):
        """Test successful port forward start."""
        adapter = KubectlAdapter()
        connection_info = ConnectionInfo.kubectl(
            resource_name='my-service',
            namespace='default'
        )
        
        mock_process = MagicMock()
        mock_process.pid = 12345
        
        mock_psutil_process = MagicMock()
        mock_psutil_process.is_running.return_value = True
        mock_psutil_process.status.return_value = 'running'
        
        with patch('subprocess.Popen', return_value=mock_process):
            with patch('psutil.Process', return_value=mock_psutil_process):
                with patch('asyncio.sleep'):
                    pid = await adapter.start_port_forward(8080, 80, connection_info)
                    assert pid == 12345

    @pytest.mark.asyncio
    async def test_start_port_forward_kubectl_not_found(self):
        """Test port forward start when kubectl is not found."""
        adapter = KubectlAdapter()
        connection_info = ConnectionInfo.kubectl(
            resource_name='my-service',
            namespace='default'
        )
        
        with patch('subprocess.Popen', side_effect=FileNotFoundError()):
            with pytest.raises(RuntimeError, match="kubectl command not found"):
                await adapter.start_port_forward(8080, 80, connection_info)

    @pytest.mark.asyncio
    async def test_stop_port_forward_success(self):
        """Test successful port forward stop."""
        adapter = KubectlAdapter()
        
        mock_psutil_process = MagicMock()
        mock_psutil_process.terminate.return_value = None
        mock_psutil_process.wait.return_value = None
        
        with patch('psutil.Process', return_value=mock_psutil_process):
            await adapter.stop_port_forward(12345)
            mock_psutil_process.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_port_forward_process_not_found(self):
        """Test port forward stop when process is not found."""
        adapter = KubectlAdapter()
        
        with patch('psutil.Process', side_effect=psutil.NoSuchProcess(12345)):
            # Should not raise an exception
            await adapter.stop_port_forward(12345)

    @pytest.mark.asyncio
    async def test_is_process_running_true(self):
        """Test is_process_running when process is running."""
        adapter = KubectlAdapter()
        
        with patch('psutil.pid_exists', return_value=True):
            result = await adapter.is_process_running(12345)
            assert result is True

    @pytest.mark.asyncio
    async def test_is_process_running_false(self):
        """Test is_process_running when process is not running."""
        adapter = KubectlAdapter()
        
        with patch('psutil.pid_exists', return_value=False):
            result = await adapter.is_process_running(12345)
            assert result is False


@pytest.mark.integration
class TestKubectlAdapterIntegration:
    """Integration tests for KubectlAdapter."""

    @pytest.mark.asyncio
    async def test_kubectl_adapter_factory_integration(self):
        """Test kubectl adapter works with adapter factory."""
        from src.localport.infrastructure.adapters.adapter_factory import AdapterFactory
        from src.localport.domain.enums import ForwardingTechnology
        
        factory = AdapterFactory()
        
        # Test kubectl adapter creation
        kubectl_adapter = await factory.create_adapter('kubectl')
        assert kubectl_adapter is not None
        assert kubectl_adapter.get_adapter_name() == "Kubectl Port Forward"
        
        # Test adapter for kubectl technology
        tech_adapter = await factory.get_adapter(ForwardingTechnology.KUBECTL)
        assert tech_adapter is not None
        assert tech_adapter.get_adapter_name() == "Kubectl Port Forward"

    @pytest.mark.asyncio
    async def test_kubectl_validation_integration(self):
        """Test kubectl validation with real kubectl command (if available)."""
        adapter = KubectlAdapter()
        
        # Test with valid configuration
        connection_info = ConnectionInfo.kubectl(
            resource_name='kubernetes',
            namespace='default',
            resource_type='service'
        )
        
        errors = await adapter.validate_connection_info(connection_info)
        # Should not have validation errors for basic config
        assert isinstance(errors, list)

    @pytest.mark.asyncio
    async def test_interface_compliance_integration(self):
        """Test that kubectl adapter fully complies with the interface."""
        adapter = KubectlAdapter()
        
        # Test all required methods exist and are callable
        required_methods = [
            'start_port_forward',
            'stop_port_forward',
            'is_port_forward_running',
            'validate_connection_info',
            'get_adapter_name',
            'get_required_tools',
            'check_prerequisites'
        ]
        
        for method_name in required_methods:
            assert hasattr(adapter, method_name)
            method = getattr(adapter, method_name)
            assert callable(method)
        
        # Test method return types
        assert isinstance(adapter.get_adapter_name(), str)
        assert isinstance(adapter.get_required_tools(), list)
        
        # Test async methods don't raise immediately
        connection_info = ConnectionInfo.kubectl(resource_name='test')
        try:
            await adapter.validate_connection_info(connection_info)
            await adapter.check_prerequisites()
        except Exception as e:
            # Methods should not raise exceptions for basic calls
            pytest.fail(f"Method raised unexpected exception: {e}")
