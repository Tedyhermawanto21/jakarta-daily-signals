from jds.run_dbt import dbt_env_from_url, with_dirs


def test_dbt_env_from_url_parses_all_parts():
    env = dbt_env_from_url(
        "postgresql://jds_owner:p%40ss@ep-x.ap-southeast-1.aws.neon.tech/jds"
        "?sslmode=require&channel_binding=require"
    )
    assert env == {
        "DBT_PG_HOST": "ep-x.ap-southeast-1.aws.neon.tech",
        "DBT_PG_PORT": "5432",
        "DBT_PG_USER": "jds_owner",
        "DBT_PG_PASSWORD": "p@ss",  # URL-decoded
        "DBT_PG_DBNAME": "jds",
        "DBT_PG_SSLMODE": "require",
    }


def test_with_dirs_adds_project_and_profiles_dir_once():
    args = with_dirs(["build"])
    assert args[0] == "build"
    assert args.count("--project-dir") == 1 and args.count("--profiles-dir") == 1
    assert with_dirs(["build", "--project-dir", "x", "--profiles-dir", "y"]) == [
        "build",
        "--project-dir",
        "x",
        "--profiles-dir",
        "y",
    ]
