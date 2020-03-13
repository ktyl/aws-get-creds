from pathlib import Path
import os
import configparser
import boto3
import json

with open('config.json') as json_file:
    data = json.load(json_file)
    mfa_serial = data["mfa-serial"]
    profiles = data['profiles']

configpath = os.path.join(str(Path.home()), ".aws/credentials")

config = configparser.ConfigParser()
config.read(configpath)

assume_profile_config = {}
for profile in profiles:
    if not profile in config.sections():
        print(f"Profile {profile} is not defined")
        continue

    parent_profile = config[profile]["source_profile"]
    if parent_profile is not None:
        if not parent_profile in assume_profile_config:
            assume_profile_config[parent_profile] = []
        assume_profile_config[parent_profile].append(
            {
                "profile": profile,
                "arn": config[profile]["role_arn"]
            }
        )

for source_profile in assume_profile_config:
    token = input(f"Enter your MFA token for profile `{source_profile}`: ")
    session = boto3.Session(profile_name=source_profile)
    client = session.client("sts")
    mfa_creds = client.get_session_token(
        DurationSeconds=900,
        SerialNumber=mfa_serial,
        TokenCode=token
    )

    client = boto3.client(
        "sts", 
        aws_access_key_id=mfa_creds["Credentials"]["AccessKeyId"],
        aws_secret_access_key=mfa_creds["Credentials"]["SecretAccessKey"],
        aws_session_token=mfa_creds["Credentials"]["SessionToken"])

    
    for source_profile, assumed_roles in assume_profile_config.items():
        for role in assumed_roles:
            response = client.assume_role(
                RoleArn=role["arn"],
                RoleSessionName=role["profile"] + "-mfa",
                DurationSeconds=3600,
            )

            config[role["profile"] + "-mfa"] = {
                "aws_access_key_id": response["Credentials"]["AccessKeyId"],
                "aws_secret_access_key": response["Credentials"]["SecretAccessKey"],
                "aws_session_token": response["Credentials"]["SessionToken"],
            }

with open(configpath, 'w') as configfile:
    config.write(configfile)
    print(f"Configuration written to `{configpath}`")