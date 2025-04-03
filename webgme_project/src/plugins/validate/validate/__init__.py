import sys
import logging
import os
import yaml
import subprocess
from webgme_bindings import PluginBase
from .utils import WebGMEUtils

# Setup a logger
logger = logging.getLogger('validate')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class validate(PluginBase):
    def main(self):
        core = self.core
        root_node = self.root_node
        active_node = self.active_node

        topology_name = core.get_attribute(active_node, 'name')
        logger.info(f'ActiveNode at "{core.get_path(active_node)}" has name "{topology_name}"')

        commit_info = self.util.save(root_node, self.commit_hash, 'master', 'Python plugin updated the model')
        logger.info(f'Committed: {commit_info}')

        self.plugin_utils = WebGMEUtils(core, root_node, active_node, self.META)

        experiment_dir = self.get_experiment_directory(topology_name)
        config_file_path = os.path.join(experiment_dir, 'config.fab')
        

        if not os.path.exists(config_file_path):
            msg = f"FabFed config file not found at: {config_file_path}"
            logger.error(msg)
            self.create_message(active_node, msg, 'error')
            self.result_set_success(False)
            return

        # YAML Syntax Check (optional but useful)
        if not self.check_yaml_syntax(config_file_path):
            self.result_set_success(False)
            return

        # Run FabFed CLI validation
        is_valid = self.run_fabfed_validation(session_name=topology_name, config_dir=experiment_dir)
        self.result_set_success(is_valid)

    def get_experiment_directory(self, topology_name):
        """
        Get the directory where the experiment's config lives.
        """
        return os.path.join("Experiments", topology_name)

    def check_yaml_syntax(self, config_file_path):
        """
        Check if the config file is valid YAML.
        """
        try:
            with open(config_file_path, 'r') as f:
                yaml.safe_load(f)
            return True
        except yaml.YAMLError as e:
            error_msg = f"YAML syntax error in config file: {e}"
            logger.error(error_msg)
            self.create_message(self.active_node, error_msg, 'error')
            return False

    def run_fabfed_validation(self, session_name, config_dir):
        """
        Run the FabFed CLI validate command and report results to WebGME.
        """
        try:
            cmd = ["fabfed", "workflow", "-s", session_name, "-c", config_dir, "-validate"]
            logger.info(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                success_msg = f"✅ FabFed validation successful:\n{result.stdout}"
                logger.info(success_msg)
                self.create_message(self.active_node, success_msg, 'info')
                return True
            else:
                error_msg = f"❌ FabFed validation failed:\n{result.stderr}"
                logger.error(error_msg)
                self.create_message(self.active_node, error_msg, 'error')
                return False

        except Exception as e:
            error_msg = f"Error executing FabFed validation: {e}"
            logger.error(error_msg)
            self.create_message(self.active_node, error_msg, 'error')
            return False
