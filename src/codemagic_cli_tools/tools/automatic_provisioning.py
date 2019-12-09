#!/usr/bin/env python3

from __future__ import annotations

import argparse
from typing import List
from typing import Optional

from codemagic_cli_tools import cli
from codemagic_cli_tools.apple import AppStoreConnectApiError
from codemagic_cli_tools.apple.app_store_connect import AppStoreConnectApiClient
from codemagic_cli_tools.apple.app_store_connect import IssuerId
from codemagic_cli_tools.apple.app_store_connect import KeyIdentifier
from codemagic_cli_tools.apple.resources import BundleId
from codemagic_cli_tools.apple.resources import Certificate
from codemagic_cli_tools.apple.resources import Profile
from codemagic_cli_tools.apple.resources import BundleIdPlatform
from codemagic_cli_tools.apple.resources import CertificateType
from codemagic_cli_tools.apple.resources import Device
from codemagic_cli_tools.apple.resources import DeviceStatus
from codemagic_cli_tools.apple.resources import ProfileType
from codemagic_cli_tools.apple.resources import ResourceId
from codemagic_cli_tools.cli import Colors
from .provisioning.automatic_provisioning_arguments import AutomaticProvisioningArgument
from .provisioning.automatic_provisioning_arguments import BundleIdArgument
from .provisioning.automatic_provisioning_arguments import CertificateArgument
from .provisioning.automatic_provisioning_arguments import CommonArgument
from .provisioning.automatic_provisioning_arguments import DeviceArgument
from .provisioning.automatic_provisioning_arguments import ProfileArgument
from .provisioning.base_provisioning import BaseProvisioning


class AutomaticProvisioningError(cli.CliAppException):
    pass


@cli.common_arguments(
    AutomaticProvisioningArgument.LOG_REQUESTS,
    AutomaticProvisioningArgument.ISSUER_ID,
    AutomaticProvisioningArgument.KEY_IDENTIFIER,
    AutomaticProvisioningArgument.PRIVATE_KEY,
    AutomaticProvisioningArgument.PRIVATE_KEY_PATH,
)
class AutomaticProvisioning(BaseProvisioning):
    """
    Utility to download code signing certificates and provisioning profiles
    from Apple Developer Portal using App Store Connect API to perform iOS code signing.
    """

    def __init__(self,
                 key_identifier: KeyIdentifier,
                 issuer_id: IssuerId,
                 private_key: str,
                 log_requests: bool = False,
                 **kwargs):
        super().__init__(**kwargs)
        self.api_client = AppStoreConnectApiClient(key_identifier, issuer_id, private_key, log_requests=log_requests)

    @classmethod
    def from_cli_args(cls, cli_args: argparse.Namespace):
        key_identifier_argument = AutomaticProvisioningArgument.KEY_IDENTIFIER.from_args(cli_args)
        issuer_id_argument = AutomaticProvisioningArgument.ISSUER_ID.from_args(cli_args)
        if issuer_id_argument is None:
            raise AutomaticProvisioningArgument.ISSUER_ID.raise_argument_error()
        if key_identifier_argument is None:
            raise AutomaticProvisioningArgument.KEY_IDENTIFIER.raise_argument_error()

        private_key_argument = AutomaticProvisioningArgument.PRIVATE_KEY.from_args(cli_args)
        private_key_path_argument = AutomaticProvisioningArgument.PRIVATE_KEY_PATH.from_args(cli_args)
        if private_key_argument is None and private_key_path_argument is None:
            raise AutomaticProvisioningArgument.PRIVATE_KEY.raise_argument_error()
        if private_key_argument is not None and private_key_path_argument is not None:
            arguments = (AutomaticProvisioningArgument.PRIVATE_KEY, AutomaticProvisioningArgument.PRIVATE_KEY_PATH)
            given_arguments = ' and '.join(map(lambda k: Colors.CYAN(k.key.upper()), arguments))
            raise AutomaticProvisioningArgument.PRIVATE_KEY.raise_argument_error(
                f'Both {given_arguments} were given. Choose one.')

        if private_key_argument:
            private_key = private_key_argument.value
        else:
            private_key = private_key_path_argument.value.expanduser().read_text()

        return AutomaticProvisioning(
            issuer_id=issuer_id_argument.value,
            key_identifier=key_identifier_argument.value,
            private_key=private_key,
            profiles_directory=cli_args.profiles_directory,
            certificates_directory=cli_args.certificates_directory,
            log_requests=cli_args.log_requests,
        )

    def _list_resources(self, resource_filter, listing_function, resource_name):
        try:
            resources = listing_function(resource_filter=resource_filter)
        except AppStoreConnectApiError as api_error:
            raise AutomaticProvisioningError(str(api_error))

        self.logger.info(f'Found {len(resources)} {resource_name} matching {resource_filter}')
        return resources

    @cli.action('list-devices',
                BundleIdArgument.PLATFORM,
                DeviceArgument.DEVICE_NAME,
                DeviceArgument.DEVICE_STATUS,
                CommonArgument.JSON_OUTPUT)
    def list_devices(self,
                     platform: Optional[BundleIdPlatform] = None,
                     device_name: Optional[str] = None,
                     device_status: Optional[DeviceStatus] = None,
                     json_output: Optional[bool] = False,
                     print_resources: bool = True) -> List[Device]:
        """
        List Devices from Apple Developer portal matching given constraints.
        """

        device_filter = self.api_client.devices.Filter(
            name=device_name, platform=platform, status=device_status)
        devices = self._list_resources(device_filter, self.api_client.devices.list, 'Devices')

        if print_resources:
            BundleId.print_resources(devices, json_output)
        return devices

    @cli.action('create-bundle-id',
                BundleIdArgument.BUNDLE_ID_IDENTIFIER,
                BundleIdArgument.BUNDLE_ID_NAME,
                BundleIdArgument.PLATFORM,
                CommonArgument.JSON_OUTPUT)
    def create_bundle_id(self,
                         bundle_id_identifier: str,
                         bundle_id_name: Optional[str] = None,
                         platform: BundleIdPlatform = BundleIdPlatform.IOS,
                         json_output: Optional[bool] = False,
                         print_resources: bool = True) -> BundleId:
        """
        Create Bundle ID in Apple Developer portal for specifier identifier.
        """

        if bundle_id_name is None:
            bundle_id_name = bundle_id_identifier.replace('.', ' ')
        self.logger.info(
            f'Creating new Bundle ID "{bundle_id_identifier}" with name "{bundle_id_name}" for platform {platform}')
        try:
            bundle_id = self.api_client.bundle_ids.register(bundle_id_identifier, bundle_id_name, platform)
        except AppStoreConnectApiError as api_error:
            raise AutomaticProvisioningError(str(api_error))
        self.logger.info(f'Created Bundle ID {bundle_id.id}')

        if print_resources:
            bundle_id.print(json_output)
        return bundle_id

    @cli.action('list-bundle-ids',
                BundleIdArgument.BUNDLE_ID_IDENTIFIER_OPTIONAL,
                BundleIdArgument.BUNDLE_ID_NAME,
                BundleIdArgument.PLATFORM,
                CommonArgument.JSON_OUTPUT)
    def list_bundle_ids(self,
                        bundle_id_identifier: Optional[str] = None,
                        bundle_id_name: Optional[str] = None,
                        platform: BundleIdPlatform = BundleIdPlatform.IOS,
                        json_output: Optional[bool] = False,
                        print_resources: bool = True) -> List[BundleId]:
        """
        List Bundle IDs from Apple Developer portal matching given constraints.
        """

        bundle_id_filter = self.api_client.bundle_ids.Filter(
            identifier=bundle_id_identifier, name=bundle_id_name, platform=platform)
        bundle_ids = self._list_resources(bundle_id_filter, self.api_client.bundle_ids.list, 'Bundle IDs')
        if not bundle_ids:
            error_message = f'Did not find any Bundle IDs matching specified filters: {bundle_id_filter}'
            raise AutomaticProvisioningError(error_message)

        if print_resources:
            BundleId.print_resources(bundle_ids, json_output)
        return bundle_ids

    @cli.action('find-bundle-ids',
                BundleIdArgument.BUNDLE_ID_IDENTIFIER,
                BundleIdArgument.PLATFORM,
                CommonArgument.CREATE_RESOURCE,
                CommonArgument.JSON_OUTPUT)
    def find_bundle_ids(self,
                        bundle_id_identifier: str,
                        platform: BundleIdPlatform = BundleIdPlatform.IOS,
                        create_resource: Optional[bool] = False,
                        json_output: Optional[bool] = False,
                        print_resource: bool = True) -> List[BundleId]:
        """
        Find Bundle IDs from Apple Developer portal for specified identifier.
        """

        try:
            bundle_ids = self.list_bundle_ids(
                bundle_id_identifier=bundle_id_identifier,
                platform=platform,
                json_output=json_output,
                print_resources=True)
        except AutomaticProvisioningError:
            if not create_resource:
                raise
            self.logger.info(f'Bundle ID for identifier {bundle_id_identifier} not found.')
            bundle_id = self.create_bundle_id(
                bundle_id_identifier, json_output=json_output, platform=platform, print_resources=False)
            bundle_ids = [bundle_id]

        if print_resource:
            BundleId.print_resources(bundle_ids, json_output)
        return bundle_ids

    @cli.action('get-bundle-id',
                BundleIdArgument.BUNDLE_ID_RESOURCE_ID,
                CommonArgument.JSON_OUTPUT)
    def get_bundle_id(self,
                      bundle_id_resource_id: ResourceId,
                      json_output: Optional[bool] = False,
                      print_resource: bool = True) -> BundleId:
        """
        Get specified Bundle ID from Apple Developer portal.
        """
        self.logger.info(f'Get Bundle ID {bundle_id_resource_id}')
        try:
            bundle_id = self.api_client.bundle_ids.read(bundle_id_resource_id)
        except AppStoreConnectApiError as api_error:
            raise AutomaticProvisioningError(str(api_error))

        if print_resource:
            bundle_id.print(json_output)
        return bundle_id

    @cli.action('delete-bundle-id',
                BundleIdArgument.BUNDLE_ID_RESOURCE_ID,
                CommonArgument.IGNORE_NOT_FOUND)
    def delete_bundle_id(self,
                         bundle_id_resource_id: ResourceId,
                         ignore_not_found: Optional[bool] = False) -> None:
        """
        Delete specified Bundle ID from Apple Developer portal.
        """
        self.logger.info(f'Delete Bundle ID {bundle_id_resource_id}')
        try:
            self.api_client.bundle_ids.delete(bundle_id_resource_id)
        except AppStoreConnectApiError as api_error:
            if ignore_not_found and api_error.status_code == 404:
                self.logger.info(f'Bundle ID {bundle_id_resource_id} does not exist, did not delete.')
                return
            raise AutomaticProvisioningError(str(api_error))
        else:
            self.logger.info(f'Successfully deleted Bundle ID {bundle_id_resource_id}')

    @cli.action('fetch-certificates',
                CertificateArgument.CERTIFICATE_TYPE,
                CertificateArgument.DISPLAY_NAME,
                CommonArgument.CREATE_RESOURCE,
                CommonArgument.JSON_OUTPUT,
                CommonArgument.SAVE)
    def fetch_certificates(self,
                           certificate_type: Optional[CertificateType] = None,
                           display_name: Optional[str] = None,
                           create_resource: bool = False,
                           json_output: bool = False,
                           save: bool = False,
                           print_resources: bool = True) -> List[Certificate]:
        """
        Fetch code signing certificates from Apple Developer Portal for offline use
        """
        certificate_filter = self.api_client.certificates.Filter(
            certificate_type=certificate_type,
            display_name=display_name)
        try:
            certificates = self._list_resources(certificate_filter, self.api_client.certificates.list, 'Certificates')
        except AutomaticProvisioningError:
            if not create_resource:
                raise
            self.logger.info(f'Certificate with type {certificate_type} not found.')
            # TODO: create certificate
            raise NotImplemented

        if print_resources:
            Certificate.print_resources(certificates, json_output)
        return certificates

    @cli.action('fetch',
                BundleIdArgument.BUNDLE_ID_IDENTIFIER,
                ProfileArgument.PROFILE_TYPE,
                BundleIdArgument.PLATFORM,
                DeviceArgument.NO_AUTO_PROVISION,
                CommonArgument.CREATE_RESOURCE,
                CommonArgument.JSON_OUTPUT)
    def fetch_signing_files(self,
                            bundle_id_identifier: str,
                            platform: BundleIdPlatform = BundleIdPlatform.IOS,
                            profile_type: ProfileType = ProfileType.IOS_APP_DEVELOPMENT,
                            auto_provision: Optional[bool] = True,
                            create_resource: Optional[bool] = False,
                            json_output: bool = False):
        """
        Fetch provisioning profiles and code signing certificates for Bundle ID with given
        identifier.
        """

        bundle_ids = self.find_bundle_ids(
            bundle_id_identifier,
            platform=platform,
            create_resource=create_resource,
            json_output=json_output,
            print_resource=False)
        if not bundle_ids:
            raise AutomaticProvisioningError(f'Did not find Bundle ID with identifier {bundle_id_identifier}')
        certificate_type = CertificateType.from_profile_type(profile_type)
        devices = self.list_devices(
            platform=platform, device_status=DeviceStatus.ENABLED, print_resources=False)
        certificates = self.fetch_certificates(
            certificate_type=certificate_type, create_resource=True, print_resources=False)
        profiles: List[Profile] = []  # TODO: fetch profiles
        if auto_provision:
            # TODO: update profiles with new devices
            ...
        raise NotImplemented


if __name__ == '__main__':
    AutomaticProvisioning.invoke_cli()
