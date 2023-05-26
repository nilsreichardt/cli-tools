from __future__ import annotations

from typing import TYPE_CHECKING
from typing import cast

from googleapiclient import discovery
from oauth2client.service_account import ServiceAccountCredentials

from .resource_managers.release_manager import FirebaseReleaseManager

if TYPE_CHECKING:
    from googleapiclient._apis.firebaseappdistribution.v1.resources import FirebaseAppDistributionResource
    from typing_extensions import Final


class FirebaseApiClient:
    SERVICE_NAME: Final[str] = 'firebaseappdistribution'

    def __init__(self, service_account_dict: dict):
        self.service_account_dict = service_account_dict

    @property
    def _credentials(self) -> ServiceAccountCredentials:
        return ServiceAccountCredentials.from_json_keyfile_dict(self.service_account_dict)

    @property
    def _firebase_app_distribution(self) -> FirebaseAppDistributionResource:
        return cast(
            'FirebaseAppDistributionResource',
            discovery.build(self.SERVICE_NAME, 'v1', credentials=self._credentials),
        )

    @property
    def releases(self) -> FirebaseReleaseManager:
        return FirebaseReleaseManager(self._firebase_app_distribution)
