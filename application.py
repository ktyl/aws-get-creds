from pathlib import Path
from exceptions import *
import boto3
import configparser
import os
import random
import string

class Application:

    config_path = os.path.join(str(Path.home()), ".aws/aws-get-creds.ini")
    credenials_path = os.path.join(str(Path.home()), ".aws/credentials")

    def __init__(self):
        pass

    def run(self):
        profiles = self.parse_configuration(self.config_path)
        assumed_roles = {}
        errors = False
        for source_profile, assume_config in profiles.items():
            for mfa, profiles in assume_config.items():
                client = self.get_authorized_sts_client(source_profile, mfa)
                for profile in profiles:
                    try:
                        assumed_roles[profile['name']] = self.assume_role(client, profile)
                    except Exception as e:
                        print(f"Error while assuming role for profile {profile}\n{str(e)}")
                        errors = True

        save = True
        if errors:
            response = input("There were errors while obtaining the credentials, do you want to write the credentials file anyway? [Y/N]: ")
            save = (response == "Y" or response == "y")

        if save:
            self.write_config(self.credenials_path, assumed_roles)
        else:
            print("The credentials file has not been updated.")

    def parse_configuration(self, path: str) -> dict:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Configuration file `{path}` does not exist")

        config = configparser.ConfigParser()
        config.read(path)
        profiles = {}
        for profile in config.sections():
            
            if 'source_profile' not in config[profile]:
                raise ConfigurationException(f"Missing `source_profile` configuration value for profile `{profile}` in `{path}`.")
            source_profile = config[profile]['source_profile']
            
            if 'role_arn' not in config[profile]:
                raise ConfigurationException(f"Missing `role_arn` configuration value for profile `{profile}` in `{path}`.")
            role_arn = config[profile]['role_arn']
            
            if 'mfa_serial' in config[profile]:
                mfa_serial = config[profile]['mfa_serial']
            else:
                mfa_serial = 'no-mfa' # not supported yet

            if not source_profile in profiles:
                profiles[source_profile] = {}
            if not mfa_serial in profiles[source_profile]:
                profiles[source_profile][mfa_serial] = []
            profiles[source_profile][mfa_serial].append({
                'name': profile,
                'role': role_arn
            })

        return profiles

    def get_authorized_sts_client(self, source_profile: str, mfa: str):
        token = input(f"Enter your MFA token for profile `{source_profile}`: ")
        session = boto3.Session(profile_name=source_profile)
        client = session.client("sts")
        mfa_creds = client.get_session_token(
            DurationSeconds=900,
            SerialNumber=mfa,
            TokenCode=token
        )

        return boto3.client(
            "sts", 
            aws_access_key_id=mfa_creds["Credentials"]["AccessKeyId"],
            aws_secret_access_key=mfa_creds["Credentials"]["SecretAccessKey"],
            aws_session_token=mfa_creds["Credentials"]["SessionToken"])

    def assume_role(self, client, profile):
        response = client.assume_role(
            RoleArn=profile["role"],
            RoleSessionName=profile["name"] + "-".join(random.sample(string.ascii_lowercase, 10)), # this should contain the name of the user that assumes the role
            DurationSeconds=3600,
        )

        return {
            "aws_access_key_id": response["Credentials"]["AccessKeyId"],
            "aws_secret_access_key": response["Credentials"]["SecretAccessKey"],
            "aws_session_token": response["Credentials"]["SessionToken"],
        }

    def write_config(self, path, data):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Configuration file `{path}` does not exist")

        config = configparser.ConfigParser()
        config.read(path)

        for profile, credentials in data.items():
            config[profile] = credentials

        with open(path, 'w') as configfile:
            config.write(configfile)
            print(f"Configuration written to `{path}`")