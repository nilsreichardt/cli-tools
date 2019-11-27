import pytest

from apple.resources import App
from apple.resources import ResourceType
from tests.apple.app_store_connect_api_client.endpoint_tests_base import EndpointTestsBase


@pytest.mark.skip(reason='Live App Store Connect API access')
class AppEndpointsTest(EndpointTestsBase):

    def test_list_apps(self):
        apps = self.api_client.list_apps()
        assert len(apps) > 0
        for app in apps:
            assert isinstance(app, App)
            assert app.type is ResourceType.APP
