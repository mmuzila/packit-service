# Copyright Contributors to the Packit project.
# SPDX-License-Identifier: MIT

import pytest
from copr.v3 import Client, BuildProxy, BuildChrootProxy
from flexmock import flexmock
from munch import Munch

import packit_service
from ogr.services.github import GithubProject
from packit.config import PackageConfig, JobConfig, JobType, JobConfigTriggerType
from packit.config.job_config import JobMetadataConfig
from packit_service.constants import PG_COPR_BUILD_STATUS_SUCCESS
from packit_service.models import (
    CoprBuildModel,
    SRPMBuildModel,
    PullRequestModel,
)
from packit_service.worker.events import AbstractCoprBuildEvent
from packit_service.worker.build.babysit import check_copr_build

BUILD_ID = 1300329


# FIXME: I tried but couldn't make it work
# @pytest.fixture()
# def requre_setup():
#     upgrade_import_system() \
#         .decorate(
#             where="^packit_service",
#             what="BuildProxy.get",
#             decorator=Simple.decorator_plain,
#         )
#
#     TEST_DATA_DIR = "test_data"
#     PERSISTENT_DATA_PREFIX = Path(__file__).parent.parent / TEST_DATA_DIR
#
#     test_file_name = os.path.basename(__file__).rsplit(
#         ".", 1
#     )[0]
#     testdata_dirname = PERSISTENT_DATA_PREFIX / str(test_file_name)
#     testdata_dirname.mkdir(mode=0o777, exist_ok=True)
#
#     PersistentObjectStorage().storage_file = testdata_dirname / "packit_build_752"
#
#     yield
#     PersistentObjectStorage().dump()


@pytest.fixture()
def packit_build_752():
    pr_model = PullRequestModel.get_or_create(
        pr_id=752,
        namespace="packit-service",
        repo_name="packit",
        project_url="https://github.com/packit-service/packit",
    )

    srpm_build, run_model = SRPMBuildModel.create_with_new_run(
        "asd\nqwe\n", success=True, trigger_model=pr_model
    )
    yield CoprBuildModel.create(
        build_id=str(BUILD_ID),
        commit_sha="687abc76d67d",
        project_name="packit-service-packit-752",
        owner="packit",
        web_url=(
            "https://download.copr.fedorainfracloud.org/"
            "results/packit/packit-service-packit-752"
        ),
        target="fedora-rawhide-x86_64",
        status="pending",
        run_model=run_model,
    )


def test_check_copr_build(clean_before_and_after, packit_build_752):
    flexmock(Client).should_receive("create_from_config_file").and_return(Client(None))
    flexmock(AbstractCoprBuildEvent).should_receive("get_package_config").and_return(
        PackageConfig(
            jobs=[
                JobConfig(
                    type=JobType.copr_build,
                    trigger=JobConfigTriggerType.pull_request,
                    metadata=JobMetadataConfig(
                        targets=[
                            "fedora-30-x86_64",
                            "fedora-rawhide-x86_64",
                            "fedora-31-x86_64",
                            "fedora-32-x86_64",
                        ]
                    ),
                )
            ]
        )
    )
    coprs_response = Munch(
        {
            "chroots": [
                "fedora-30-x86_64",
                "fedora-rawhide-x86_64",
                "fedora-31-x86_64",
                "fedora-32-x86_64",
            ],
            "ended_on": 1583916564,
            "id": 1300329,
            "ownername": "packit",
            "project_dirname": "packit-service-packit-752",
            "projectname": "packit-service-packit-752",
            "repo_url": (
                "https://download.copr.fedorainfracloud.org/"
                "results/packit/packit-service-packit-752"
            ),
            "source_package": {
                "name": "packit",
                "url": (
                    "https://download.copr.fedorainfracloud.org/"
                    "results/packit/packit-service-packit-752/"
                    "srpm-builds/01300329/packit-0.8.2.dev122g64ebb47-1.fc31.src.rpm"
                ),
                "version": "0.8.2.dev122+g64ebb47-1.fc31",
            },
            "started_on": 1583916315,
            "state": "succeeded",
            "submitted_on": 1583916261,
            "submitter": "packit",
        }
    )
    flexmock(BuildProxy).should_receive("get").and_return(coprs_response)

    chroot_response = Munch(
        {
            "ended_on": 1583916564,
            "name": "fedora-rawhide-x86_64",
            "result_url": "https://download.copr.fedorainfracloud.org/"
            "results/packit/packit-service-packit-752/fedora-rawhide-x86_64/"
            "01300329-packit/",
            "started_on": 1583916315,
            "state": "succeeded",
        }
    )
    flexmock(BuildChrootProxy).should_receive("get").with_args(
        BUILD_ID, "fedora-rawhide-x86_64"
    ).and_return(chroot_response)

    # Reporting
    flexmock(GithubProject).should_receive("get_pr").and_return(
        flexmock(source_project=flexmock())
    )
    flexmock(GithubProject).should_receive("get_pr_comments").and_return([])
    flexmock(GithubProject).should_receive("pr_comment").and_return()
    flexmock(GithubProject).should_receive("set_commit_status").and_return().once()
    flexmock(GithubProject).should_receive("get_git_urls").and_return(
        {"git": "https://github.com/packit-service/packit.git"}
    )
    flexmock(packit_service.worker.build.copr_build).should_receive(
        "get_valid_build_targets"
    ).and_return(
        {
            "fedora-33-x86_64",
            "fedora-32-x86_64",
            "fedora-31-x86_64",
            "fedora-rawhide-x86_64",
        }
    )

    check_copr_build(BUILD_ID)
    assert packit_build_752.status == PG_COPR_BUILD_STATUS_SUCCESS
