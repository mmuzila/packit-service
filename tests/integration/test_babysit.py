# Copyright Contributors to the Packit project.
# SPDX-License-Identifier: MIT

from copr.v3 import Client
from flexmock import flexmock

from packit.config import PackageConfig, JobConfig, JobType, JobConfigTriggerType
from packit_service.models import CoprBuildModel, JobTriggerModelType
from packit_service.worker.events import AbstractCoprBuildEvent
from packit_service.worker.build.babysit import check_copr_build
from packit_service.worker.handlers import CoprBuildEndHandler
from packit_service.constants import COPR_API_SUCC_STATE

from packit_service.worker.events.event import EventData
from packit_service.worker.handlers import JobHandler
from packit_service.worker.build.copr_build import CoprBuildJobHelper
from datetime import datetime
from munch import Munch


def test_check_copr_build_no_build():
    flexmock(CoprBuildModel).should_receive("get_all_by_build_id").with_args(
        1
    ).and_return([])
    assert check_copr_build(build_id=1)


def test_check_copr_build_not_ended():
    flexmock(CoprBuildModel).should_receive("get_all_by_build_id").with_args(
        1
    ).and_return([flexmock()])
    flexmock(Client).should_receive("create_from_config_file").and_return(
        flexmock(
            build_proxy=flexmock()
            .should_receive("get")
            .with_args(1)
            .and_return(flexmock(ended_on=False))
            .mock()
        )
    )
    assert not check_copr_build(build_id=1)


def test_check_copr_build_already_successful():
    flexmock(CoprBuildModel).should_receive("get_all_by_build_id").with_args(
        1
    ).and_return([flexmock(status="success")])
    flexmock(Client).should_receive("create_from_config_file").and_return(
        flexmock(
            build_proxy=flexmock()
            .should_receive("get")
            .with_args(1)
            .and_return(flexmock(ended_on="timestamp", state="completed"))
            .mock()
        )
    )
    assert check_copr_build(build_id=1)


def test_check_copr_build_updated():
    flexmock(CoprBuildModel).should_receive("get_by_build_id").and_return()
    flexmock(CoprBuildModel).should_receive("get_all_by_build_id").with_args(
        1
    ).and_return(
        [
            flexmock(
                status="pending",
                target="the-target",
                owner="the-owner",
                project_name="the-project-name",
                commit_sha="123456",
                job_trigger=flexmock(type=JobTriggerModelType.pull_request),
                srpm_build=flexmock(url=None)
                .should_receive("set_url")
                .with_args("https://some.host/my.srpm")
                .mock(),
            )
            .should_receive("get_trigger_object")
            .and_return(
                flexmock(
                    project=flexmock(
                        repo_name="repo_name",
                        namespace="the-namespace",
                        project_url="https://github.com/the-namespace/repo_name",
                    ),
                    pr_id=5,
                    job_config_trigger_type=JobConfigTriggerType.pull_request,
                    job_trigger_model_type=JobTriggerModelType.pull_request,
                    id=123,
                )
            )
            .mock()
        ]
    )
    flexmock(Client).should_receive("create_from_config_file").and_return(
        flexmock(
            build_proxy=flexmock()
            .should_receive("get")
            .with_args(1)
            .and_return(
                flexmock(
                    ended_on=True,
                    state="completed",
                    source_package={
                        "name": "source_package_name",
                        "url": "https://some.host/my.srpm",
                    },
                )
            )
            .mock(),
            build_chroot_proxy=flexmock()
            .should_receive("get")
            .with_args(1, "the-target")
            .and_return(flexmock(ended_on="timestamp", state="completed"))
            .mock(),
        )
    )
    flexmock(AbstractCoprBuildEvent).should_receive("get_package_config").and_return(
        PackageConfig(
            jobs=[
                JobConfig(type=JobType.build, trigger=JobConfigTriggerType.pull_request)
            ]
        )
    )
    flexmock(CoprBuildEndHandler).should_receive("run").and_return().once()
    assert check_copr_build(build_id=1)


def test_set_copr_built_packages():

    copr_response = Munch(
        {
            "packages": [
                {
                    "arch": "noarch",
                    "epoch": 0,
                    "name": "package-name",
                    "release": "2.fc36",
                    "version": "0.1.0",
                },
                {
                    "arch": "src",
                    "epoch": 0,
                    "name": "package-name",
                    "release": "2.fc36",
                    "version": "0.1.0",
                },
            ],
            "__response__": flexmock(),
            "__proxy__": flexmock(),
        }
    )

    copr_build = flexmock(
        id=1,
        status="pending",
        target="the-target",
        owner="the-owner",
        project_name="the-project-name",
        task_accepted_time=datetime.now(),
        commit_sha="123456",
        job_trigger=flexmock(type=JobTriggerModelType.pull_request),
        srpm_build=flexmock(url=None)
        .should_receive("set_url")
        .with_args("https://some.host/my.srpm"),
    )
    copr_build.should_receive("get_trigger_object").and_return(
        flexmock(
            project=flexmock(
                repo_name="repo_name",
                namespace="the-namespace",
                project_url="https://github.com/the-namespace/repo_name",
            ),
            pr_id=5,
            job_config_trigger_type=JobConfigTriggerType.pull_request,
            job_trigger_model_type=JobTriggerModelType.pull_request,
            id=123,
        )
    )
    copr_build.should_receive("set_timestamp").and_return()
    copr_build.should_receive("set_end_time").and_return()
    copr_build.should_receive("set_status").and_return()
    copr_build.should_receive("set_built_packages").with_args(copr_response.packages)

    flexmock(CoprBuildModel).should_receive("get_by_build_id").with_args(
        "1", "the-target"
    ).and_return(copr_build)

    flexmock(Client).should_receive("create_from_config_file").and_return(
        flexmock(
            build_chroot_proxy=flexmock()
            .should_receive("get_built_packages")
            .with_args(1, "the-target")
            .and_return(copr_response)
            .mock()
        )
    )
    event = flexmock(AbstractCoprBuildEvent)
    event.should_receive("get_package_config").and_return(
        PackageConfig(
            jobs=[
                JobConfig(type=JobType.build, trigger=JobConfigTriggerType.pull_request)
            ]
        )
    )
    event.should_receive("from_event_dict").and_return(
        flexmock(
            build_id=1,
            chroot="the-target",
            timestamp=datetime.now().timestamp(),
            status=COPR_API_SUCC_STATE,
            pr_id=5,
        )
    )

    package_config = PackageConfig(
        jobs=[JobConfig(type=JobType.build, trigger=JobConfigTriggerType.pull_request)]
    )
    job_config = JobConfig(
        type=JobType.build, trigger=JobConfigTriggerType.pull_request
    )
    flexmock(EventData).should_receive("from_event_dict").and_return()
    flexmock(JobHandler).should_receive("project").and_return()

    flexmock(CoprBuildEndHandler).should_receive("set_srpm_url").and_return()
    flexmock(CoprBuildJobHelper).should_receive(
        "report_status_to_build_for_chroot"
    ).and_return()

    copr_build_end_handler = CoprBuildEndHandler(
        package_config=package_config, job_config=job_config, event=event
    )
    copr_build_end_handler.run()
