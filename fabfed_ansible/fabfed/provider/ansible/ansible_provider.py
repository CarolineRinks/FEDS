import os
import logging
from fabfed.model import Service
from fabfed.provider.api.provider import Provider
from fabfed.util.constants import Constants
from fabfed.util.utils import get_inventory_dir
from fabfed.provider.ansible.util.ansible_helper import AnsibleRunnerHelper

# Define constants for Ansible tags
APT_TAG = "apt-installer"
PIP_TAG = "pip-install"

class ansibleService(Service):
    def __init__(self, *, label, name, nodes, provider, playbook_path, logger: logging.Logger):
        super().__init__(label=label, name=name)
        self.logger = logger
        self._nodes = nodes
        self._provider = provider
        self.created = False
        self.playbook_path = playbook_path

    def _do_ansible(self, playbook_path, extra_vars=None, limit=""):
        """
        Executes Ansible playbooks with specific tags and extra variables.
        """
        try:
            def _helper(host_file, extra_vars=dict(), limit=""):
                script_dir = os.path.dirname(__file__)
                helper = AnsibleRunnerHelper(host_file, self.logger)
                helper.set_extra_vars(extra_vars)
                helper.run_playbook(playbook_path, limit=limit)

            # Get inventory and extra vars
            friendly_name = self._provider.name
            host_file = get_inventory_dir(friendly_name)
            if extra_vars is None:
                extra_vars = {}

            _helper(host_file, extra_vars, limit)

        except Exception as e:
            self.logger.error(f"Ansible execution failed: {e}")
            raise

    def create(self,playbook_path):
        """
        Executes the roles to install apt and pip packages.
        """
        self.logger.info(f"--------- IN CREATE METHOD !!! Creating service {self.name} using {self._provider.label}------------")
        try:
            self._do_ansible(playbook_path)
            self.logger.info(f"Service {self.name} with {self._nodes}")
            self.created = True
        except Exception as e:
            self.logger.error(f"Failed to create service {self.name}: {e}")
            raise

    def delete(self):
        """
        Placeholder for delete functionality.
        """
        self.logger.info(f"Service {self.name} deleted.")

from fabfed.util.utils import get_logger

logger: logging.Logger = get_logger()

class ansibleProvider(Provider):

    def __init__(self, *, type, label, name, config: dict):
        super().__init__(type=type, label=label, name=name, logger=logger, config=config)
        # credential_file = self.config.get(Constants.CREDENTIAL_FILE)

        # if credential_file:
        #     from fabfed.util import utils

        #     profile = self.config.get(Constants.PROFILE)
        #     if not profile:
        #         raise ValueError("Profile is missing in the configuration")

        #     config = utils.load_yaml_from_file(credential_file)
        #     if profile not in config:
        #         raise ValueError(f"Profile '{profile}' not found in credential file")

        #     self.config = config[profile]
        # else:
        #     raise ValueError("Credential file is missing in the configuration")
    def setup_environment(self):
        # Placeholder implementation (adjust as needed)
        pass
    
    def _validate_resource(self, resource: dict):
        assert resource.get(Constants.LABEL)
        assert resource.get(Constants.RES_TYPE) in Constants.RES_SUPPORTED_TYPES
        assert resource.get(Constants.RES_NAME_PREFIX)
        assert resource.get("playbook_path")
        creation_details = resource[Constants.RES_CREATION_DETAILS]

        # count was set to zero 
        if not creation_details['in_config_file']:
            # TODO HANDLE UNINSTALL OF ansible ON NODES ...
            return

        # assert resource.get(Constants.RES_COUNT, 1)
        # assert resource.get(Constants.RES_IMAGE)
        self.logger.info(f"Validated:OK Resource={self.name} using {self.label}")

    def do_add_resource(self, *, resource: dict):
        """
        Adds the ansible service resource.
        """
        nodes = resource.get("node", [])
        playbook_path = resource.get("playbook_path")
        if not nodes:
            raise ValueError("No nodes specified for the resource")
        if not playbook_path:
            raise ValueError("No playbook path specified for the resource")

        service_name = f"{self.name}-{resource.get('label')}"
        service = ansibleService(
            label=resource.get("label"),
            name=service_name,
            nodes=nodes,
            playbook_path=playbook_path,
            provider=self,
            logger=self.logger,
        )
        self._services.append(service)
        try:
            self.logger.info(f"--------- IN DO ADD RESOURCE!!!! Adding resource={self.name} using {self.label}----------")
            # service.create(playbook_path=playbook_path)
            self.resource_listener.on_added(source=self, provider=self, resource=service)
        except Exception as e:
            self.logger.error(f"Failed to add resource: {e}")
            raise

    def do_create_resource(self, *, resource: dict):
        """
        Called by add_resource(self, *, resource: dict) if resource has no external dependencies
        @param resource: resource attributes
        """
        self
        label = resource.get(Constants.LABEL)
        states = resource.get(Constants.SAVED_STATES, [])
        playbook_path = resource.get("playbook_path")
        created = any(s.attributes.get('created', False) for s in states)

        self.logger.info(f"Creating resource={self.name} using {self.label}")

        temp = [service for service in self.services if service.label == label]

        for service in temp:
        #     if created:
        #  self.logger.info(f"Service {label} is already in created state, skipping create task")
        #         service.created = True
        #     else:
            self.logger.info(f"--------- IN DO CREATE RESOURCE!!!! Creating resource={self.name} using {self.label}----------")
            service.create(playbook_path=playbook_path)
            self.resource_listener.on_created(source=self, provider=self, resource=service)

    def do_delete_resource(self, *, resource: dict):
        self.logger.info(f"Deleting resource={resource} using {self.label}")

        nodes = resource.get(Constants.EXTERNAL_DEPENDENCY_STATES, [])
        service_nodes = [n.attributes.get('name') for n in nodes]
        label = resource.get(Constants.LABEL)
        states = resource.get(Constants.SAVED_STATES, [])
        states = [s for s in states if s.label == label]

        if not states:
            return

        service_name_prefix = resource.get(Constants.RES_NAME_PREFIX)
        service_name = f"{self.name}-{service_name_prefix}"
        service = ansibleService(label=label, name=service_name, nodes=service_nodes,
                               provider=self, logger=self.logger)

        service.delete()
        self.resource_listener.on_deleted(source=self, provider=self, resource=service)
