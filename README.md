# aws-get-creds

## Installation
```
pip install -r requirements.txt
```

## Configuration
* Make sure that `~/.aws/credentials` file exists in your home directory. Sample content:
```
[default]
aws_access_key_id = XXXXXXXX
aws_secret_access_key = XXXXXXXX

[foobar-hub]
aws_access_key_id = XXXXXXXX
aws_secret_access_key = XXXXXXXX

[foobar-developer]
role_arn = arn:aws:iam::XXXXXX:role/developer
source_profile = foobar-hub

[foobar-admin]
role_arn = arn:aws:iam::XXXXXX:role/admin
source_profile = foobar-hub
```

* Copy `config.json.dist` to `config.json` and fill it with the proper data.
- `mfa-serial` - your MFA device serial number (you can find it in AWS console)
- `profiles` - list of profiles you want to fetch temporary credentials for

Example:
```
{
    "mfa-serial" : "arn:aws:iam::XXXXXX:mfa/ktyl",
    "profiles" :
    [
        "foobar-developer", 
        "foobar-admin"
    ]
}
```

## Usage
```
python aws-get-creds.py
```

This will fetch the temporary credentials and store them in the global credentials file. The name of temporary profile is the same as the source profile with appended `-mfa`.

You can check if your credentials were obtained properly by executing some command, i.e.
```
aws s3 ls --profile foobar-admin-mfa
```