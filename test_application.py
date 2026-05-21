import configparser
import os
import pytest
from unittest.mock import MagicMock, patch
from application import Application
from exceptions import ConfigurationException


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_sts_session_mock(access_key="SESSION_AKID", secret_key="SESSION_SECRET", token="SESSION_TOKEN"):
    """Mock STS client whose get_session_token returns valid MFA credentials."""
    mock = MagicMock()
    mock.get_session_token.return_value = {
        "Credentials": {
            "AccessKeyId": access_key,
            "SecretAccessKey": secret_key,
            "SessionToken": token,
        }
    }
    return mock


def make_sts_role_mock(access_key="ROLE_AKID", secret_key="ROLE_SECRET", token="ROLE_TOKEN",
                       user_arn="arn:aws:iam::123456789012:user/testuser"):
    """Mock STS client that handles get_caller_identity and assume_role."""
    mock = MagicMock()
    mock.get_caller_identity.return_value = {"Arn": user_arn}
    mock.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": access_key,
            "SecretAccessKey": secret_key,
            "SessionToken": token,
        }
    }
    return mock


# ---------------------------------------------------------------------------
# parse_configuration
# ---------------------------------------------------------------------------

class TestParseConfiguration:

    def test_raises_file_not_found_for_missing_file(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="does not exist"):
            Application().parse_configuration(str(tmp_path / "nonexistent.ini"))

    def test_raises_for_missing_source_profile(self, tmp_path):
        path = tmp_path / "config.ini"
        path.write_text("[dev]\nrole_arn = arn:aws:iam::123:role/dev\n")
        with pytest.raises(ConfigurationException, match="source_profile"):
            Application().parse_configuration(str(path))

    def test_raises_for_missing_role_arn(self, tmp_path):
        path = tmp_path / "config.ini"
        path.write_text("[dev]\nsource_profile = base\n")
        with pytest.raises(ConfigurationException, match="role_arn"):
            Application().parse_configuration(str(path))

    def test_single_profile_with_mfa(self, tmp_path):
        path = tmp_path / "config.ini"
        path.write_text(
            "[dev]\n"
            "role_arn = arn:aws:iam::123:role/dev\n"
            "source_profile = base\n"
            "mfa_serial = arn:aws:iam::123:mfa/user\n"
        )
        result = Application().parse_configuration(str(path))
        assert result == {
            "base": {
                "arn:aws:iam::123:mfa/user": [
                    {"name": "dev", "role": "arn:aws:iam::123:role/dev"}
                ]
            }
        }

    def test_profile_without_mfa_uses_no_mfa_key(self, tmp_path):
        path = tmp_path / "config.ini"
        path.write_text(
            "[dev]\n"
            "role_arn = arn:aws:iam::123:role/dev\n"
            "source_profile = base\n"
        )
        result = Application().parse_configuration(str(path))
        assert "no-mfa" in result["base"]

    def test_profiles_with_same_source_and_mfa_are_grouped(self, tmp_path):
        path = tmp_path / "config.ini"
        path.write_text(
            "[dev]\nrole_arn = arn:aws:iam::123:role/dev\nsource_profile = base\nmfa_serial = arn:aws:iam::123:mfa/user\n"
            "[admin]\nrole_arn = arn:aws:iam::123:role/admin\nsource_profile = base\nmfa_serial = arn:aws:iam::123:mfa/user\n"
        )
        result = Application().parse_configuration(str(path))
        profiles = result["base"]["arn:aws:iam::123:mfa/user"]
        assert len(profiles) == 2
        assert {"name": "dev", "role": "arn:aws:iam::123:role/dev"} in profiles
        assert {"name": "admin", "role": "arn:aws:iam::123:role/admin"} in profiles

    def test_profiles_with_different_sources_create_separate_entries(self, tmp_path):
        path = tmp_path / "config.ini"
        path.write_text(
            "[dev]\nrole_arn = arn:aws:iam::111:role/dev\nsource_profile = base1\nmfa_serial = arn:aws:iam::111:mfa/user\n"
            "[admin]\nrole_arn = arn:aws:iam::222:role/admin\nsource_profile = base2\nmfa_serial = arn:aws:iam::222:mfa/user\n"
        )
        result = Application().parse_configuration(str(path))
        assert "base1" in result
        assert "base2" in result

    def test_profiles_same_source_different_mfa_are_separate(self, tmp_path):
        path = tmp_path / "config.ini"
        path.write_text(
            "[dev]\nrole_arn = arn:aws:iam::123:role/dev\nsource_profile = base\nmfa_serial = arn:aws:iam::123:mfa/alice\n"
            "[admin]\nrole_arn = arn:aws:iam::123:role/admin\nsource_profile = base\nmfa_serial = arn:aws:iam::123:mfa/bob\n"
        )
        result = Application().parse_configuration(str(path))
        assert "arn:aws:iam::123:mfa/alice" in result["base"]
        assert "arn:aws:iam::123:mfa/bob" in result["base"]



# ---------------------------------------------------------------------------
# write_config
# ---------------------------------------------------------------------------

class TestWriteConfig:

    def test_creates_directory_and_file_when_both_missing(self, tmp_path):
        path = str(tmp_path / "subdir" / "credentials")
        Application().write_config(path, {})
        assert os.path.exists(path)

    def test_creates_file_when_only_file_missing(self, tmp_path):
        path = str(tmp_path / "credentials")
        Application().write_config(path, {})
        assert os.path.exists(path)

    def test_writes_credential_values(self, tmp_path):
        path = str(tmp_path / "credentials")
        data = {"my-profile": {
            "aws_access_key_id": "AKID",
            "aws_secret_access_key": "SECRET",
            "aws_session_token": "TOKEN",
        }}
        Application().write_config(path, data)
        config = configparser.ConfigParser()
        config.read(path)
        assert config["my-profile"]["aws_access_key_id"] == "AKID"
        assert config["my-profile"]["aws_secret_access_key"] == "SECRET"
        assert config["my-profile"]["aws_session_token"] == "TOKEN"

    def test_preserves_unrelated_existing_profiles(self, tmp_path):
        path = tmp_path / "credentials"
        existing = configparser.ConfigParser()
        existing["old-profile"] = {"aws_access_key_id": "OLD"}
        with open(path, 'w') as f:
            existing.write(f)
        Application().write_config(str(path), {"new-profile": {"aws_access_key_id": "NEW"}})
        result = configparser.ConfigParser()
        result.read(str(path))
        assert "old-profile" in result.sections()
        assert "new-profile" in result.sections()

    def test_overwrites_existing_profile(self, tmp_path):
        path = tmp_path / "credentials"
        existing = configparser.ConfigParser()
        existing["my-profile"] = {"aws_access_key_id": "OLD"}
        with open(path, 'w') as f:
            existing.write(f)
        Application().write_config(str(path), {"my-profile": {"aws_access_key_id": "NEW"}})
        result = configparser.ConfigParser()
        result.read(str(path))
        assert result["my-profile"]["aws_access_key_id"] == "NEW"


# ---------------------------------------------------------------------------
# assume_role
# ---------------------------------------------------------------------------

class TestAssumeRole:

    def _make_client(self, access_key="AKID", secret_key="SECRET", token="TOKEN"):
        mock = MagicMock()
        mock.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": access_key,
                "SecretAccessKey": secret_key,
                "SessionToken": token,
            }
        }
        return mock

    def test_returns_correct_credentials(self):
        client = self._make_client()
        result = Application().assume_role(client, "user", {"role": "arn:aws:iam::123:role/dev"})
        assert result == {
            "aws_access_key_id": "AKID",
            "aws_secret_access_key": "SECRET",
            "aws_session_token": "TOKEN",
        }

    def test_session_name_starts_with_username(self):
        client = self._make_client()
        Application().assume_role(client, "alice", {"role": "arn:aws:iam::123:role/dev"})
        session_name = client.assume_role.call_args[1]["RoleSessionName"]
        assert session_name.startswith("alice")

    def test_session_names_are_unique_across_calls(self):
        client = self._make_client()
        profile = {"role": "arn:aws:iam::123:role/dev"}
        app = Application()
        app.assume_role(client, "alice", profile)
        app.assume_role(client, "alice", profile)
        names = [c[1]["RoleSessionName"] for c in client.assume_role.call_args_list]
        assert names[0] != names[1]

    def test_correct_role_arn_passed(self):
        client = self._make_client()
        Application().assume_role(client, "user", {"role": "arn:aws:iam::123:role/admin"})
        assert client.assume_role.call_args[1]["RoleArn"] == "arn:aws:iam::123:role/admin"


# ---------------------------------------------------------------------------
# get_authorized_sts_client
# ---------------------------------------------------------------------------

class TestGetAuthorizedStsClient:

    @patch("application.boto3.client")
    @patch("application.boto3.Session")
    @patch("builtins.input", return_value="123456")
    def test_prompts_for_mfa_token(self, mock_input, mock_session, mock_boto3_client):
        mock_session.return_value.client.return_value = make_sts_session_mock()
        Application().get_authorized_sts_client("base", "arn:aws:iam::123:mfa/user")
        mock_input.assert_called_once()

    @patch("application.boto3.client")
    @patch("application.boto3.Session")
    @patch("builtins.input", return_value="123456")
    def test_uses_correct_source_profile(self, mock_input, mock_session, mock_boto3_client):
        mock_session.return_value.client.return_value = make_sts_session_mock()
        Application().get_authorized_sts_client("my-profile", "arn:aws:iam::123:mfa/user")
        mock_session.assert_called_once_with(profile_name="my-profile")

    @patch("application.boto3.client")
    @patch("application.boto3.Session")
    @patch("builtins.input", return_value="654321")
    def test_passes_token_and_serial_to_get_session_token(self, mock_input, mock_session, mock_boto3_client):
        session_client = make_sts_session_mock()
        mock_session.return_value.client.return_value = session_client
        Application().get_authorized_sts_client("base", "arn:aws:iam::123:mfa/user")
        session_client.get_session_token.assert_called_once_with(
            DurationSeconds=900,
            SerialNumber="arn:aws:iam::123:mfa/user",
            TokenCode="654321",
        )

    @patch("application.boto3.client")
    @patch("application.boto3.Session")
    @patch("builtins.input", return_value="123456")
    def test_constructs_client_with_mfa_credentials(self, mock_input, mock_session, mock_boto3_client):
        session_client = make_sts_session_mock(
            access_key="MFA_AKID", secret_key="MFA_SECRET", token="MFA_TOKEN"
        )
        mock_session.return_value.client.return_value = session_client
        Application().get_authorized_sts_client("base", "arn:aws:iam::123:mfa/user")
        mock_boto3_client.assert_called_once_with(
            "sts",
            aws_access_key_id="MFA_AKID",
            aws_secret_access_key="MFA_SECRET",
            aws_session_token="MFA_TOKEN",
        )


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

class TestRun:

    INI_SINGLE = (
        "[dev]\n"
        "role_arn = arn:aws:iam::123:role/dev\n"
        "source_profile = base\n"
        "mfa_serial = arn:aws:iam::123:mfa/user\n"
    )
    INI_TWO_SAME_MFA = INI_SINGLE + (
        "[admin]\n"
        "role_arn = arn:aws:iam::123:role/admin\n"
        "source_profile = base\n"
        "mfa_serial = arn:aws:iam::123:mfa/user\n"
    )

    def _make_app(self, config_path, creds_path):
        app = Application()
        app.config_path = config_path
        app.credentials_path = creds_path
        return app

    def _setup(self, tmp_path, ini_content):
        config_path = str(tmp_path / "aws-get-creds.ini")
        creds_path = str(tmp_path / "credentials")
        with open(config_path, 'w') as f:
            f.write(ini_content)
        return config_path, creds_path

    @patch("application.boto3.client")
    @patch("application.boto3.Session")
    @patch("builtins.input", return_value="123456")
    def test_writes_credentials_on_success(self, mock_input, mock_session, mock_boto3_client, tmp_path):
        config_path, creds_path = self._setup(tmp_path, self.INI_SINGLE)
        mock_session.return_value.client.return_value = make_sts_session_mock()
        mock_boto3_client.return_value = make_sts_role_mock()
        self._make_app(config_path, creds_path).run()
        config = configparser.ConfigParser()
        config.read(creds_path)
        assert "dev" in config.sections()
        assert config["dev"]["aws_access_key_id"] == "ROLE_AKID"

    @patch("application.boto3.client")
    @patch("application.boto3.Session")
    @patch("builtins.input", return_value="123456")
    def test_raises_and_skips_write_on_sts_auth_failure(self, mock_input, mock_session, mock_boto3_client, tmp_path):
        config_path, creds_path = self._setup(tmp_path, self.INI_SINGLE)
        mock_session.return_value.client.return_value.get_session_token.side_effect = Exception("Bad MFA")
        with pytest.raises(Exception, match="errors"):
            self._make_app(config_path, creds_path).run()
        assert not os.path.exists(creds_path)

    @patch("application.boto3.client")
    @patch("application.boto3.Session")
    @patch("builtins.input", return_value="123456")
    def test_raises_and_skips_write_on_assume_role_failure(self, mock_input, mock_session, mock_boto3_client, tmp_path):
        config_path, creds_path = self._setup(tmp_path, self.INI_SINGLE)
        mock_session.return_value.client.return_value = make_sts_session_mock()
        role_client = make_sts_role_mock()
        role_client.assume_role.side_effect = Exception("Access Denied")
        mock_boto3_client.return_value = role_client
        with pytest.raises(Exception, match="errors"):
            self._make_app(config_path, creds_path).run()
        assert not os.path.exists(creds_path)

    @patch("application.boto3.client")
    @patch("application.boto3.Session")
    @patch("builtins.input", return_value="123456")
    def test_multiple_profiles_same_mfa_prompts_once(self, mock_input, mock_session, mock_boto3_client, tmp_path):
        config_path, creds_path = self._setup(tmp_path, self.INI_TWO_SAME_MFA)
        mock_session.return_value.client.return_value = make_sts_session_mock()
        mock_boto3_client.return_value = make_sts_role_mock()
        self._make_app(config_path, creds_path).run()
        config = configparser.ConfigParser()
        config.read(creds_path)
        assert "dev" in config.sections()
        assert "admin" in config.sections()
        mock_input.assert_called_once()
