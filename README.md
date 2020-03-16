# aws-get-creds
The tool fetches the temporary AWS credentials and stores them in global credentials file.

## Installation
```
pip install -r requirements.txt
```

## Configuration
In the following exampe we will configure the script to fetch the credentials for assumed `foobar-developer` and `foobar-admin` roles, using the profile `foobar-hub` as a base profile.

* Make sure that `~/.aws/credentials` file exists in your home directory and that it contains the configuration of the profile you want to assume the role from (the base profile).

Example (`~/.aws/credentials`):
```
[default]
aws_access_key_id = XXXXXXXX
aws_secret_access_key = XXXXXXXX

[foobar-hub]
aws_access_key_id = XXXXXXXX
aws_secret_access_key = XXXXXXXX
```

* Create the file `~/.aws/aws-get-creds.ini`
* Create the config section for each profile that you want to get the temporary credentials.
* provide the following values in each section:
    * `role_arn` - the arn of the role you want to get the temporary credentials for
    * `source_profile` - profile defined in the global credentials file used for assuming into the role
    * `mfa_serial` - serial number of the MFA device you want to use for 2 factor authentication

Example (`~/.aws/aws-get-creds.ini`):
```
[foobar-developer]
role_arn = arn:aws:iam::XXXXXXXX:role/developer
source_profile = foobar-hub
mfa_serial = arn:aws:iam::XXXXXXXX:mfa/ktyl

[foobar-admin]
role_arn = arn:aws:iam::XXXXXXXX:role/developer
source_profile = foobar-hub
mfa_serial = arn:aws:iam::XXXXXXXX:mfa/ktyl
```

## Usage
```
python aws-get-creds.py
```

This will fetch the temporary credentials and store them in the global credentials file. The name of temporary profile is the same as the section of the `aws-get-creds.ini` in which the corresponding role was defined.

You can check if your credentials were obtained properly by executing some command, i.e.
```
aws s3 ls --profile foobar-admin
```