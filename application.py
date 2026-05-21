from pathlib import Path
from exceptions import ConfigurationException
import boto3
import configparser
import os
import secrets

class Application:

    config_path = os.path.join(str(Path.home()), ".aws/aws-get-creds.ini")
    credentials_path = os.path.join(str(Path.home()), ".aws/credentials")

    def run(self):
        profiles = self.parse_configuration(self.config_path)
        assumed_roles = {}
        errors = False
        for source_profile, assume_config in profiles.items():
            for mfa, profiles_to_assume in assume_config.items():
                try:
                    client = self.get_authorized_sts_client(source_profile, mfa)
                    # get_caller_identity is called intentionally to embed the IAM username
                    # in each session name, making it easier to distinguish sessions created
                    # by different users when inspecting AWS CloudTrail or the IAM console.
                    caller_identity = client.get_caller_identity()
                    username = caller_identity["Arn"].split("/")[-1]
                    print(f"Authorized the profile {source_profile} using one time password, username: {username}.")
                    for profile in profiles_to_assume:
                        try:
                            assumed_roles[profile['name']] = self.assume_role(client, username, profile)
                        except Exception as e:
                            print(f"Error while assuming role for profile {profile['name']}\n{str(e)}")
                            errors = True
                except Exception as e:
                    print(f"Error while authorizing the profile {source_profile} using one time password.\n{str(e)}")
                    errors = True

        if errors:
            raise Exception("There were errors while obtaining the credentials. The credentials file has not been updated.")
        
        self.write_config(self.credentials_path, assumed_roles)

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

            if source_profile not in profiles:
                profiles[source_profile] = {}
            if mfa_serial not in profiles[source_profile]:
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

    def assume_role(self, client, session_name, profile):
        response = client.assume_role(
            RoleArn=profile["role"],
            RoleSessionName=session_name[:48] + secrets.token_hex(8),
            DurationSeconds=3600,
        )

        return {
            "aws_access_key_id": response["Credentials"]["AccessKeyId"],
            "aws_secret_access_key": response["Credentials"]["SecretAccessKey"],
            "aws_session_token": response["Credentials"]["SessionToken"],
        }

    def write_config(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            with open(path, 'w'): pass

        config = configparser.ConfigParser()
        config.read(path)

        for profile, credentials in data.items():
            config[profile] = credentials

        with open(path, 'w') as configfile:
            config.write(configfile)
            print(f"Configuration written to `{path}`")