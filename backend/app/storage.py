"""In-memory storage acting as a placeholder for a real database."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from threading import Event, Lock
from typing import Dict, Iterable, List, Optional
from uuid import uuid4

from .models import (
    Channel,
    DomainType,
    PlatformModel,
    QuickSetQuestionModel,
    QuickSetSessionModel,
    QuickSetStepModel,
    SessionModel,
    TestIssueModel,
    TestRunModel,
    VersionModel,
)


def _version_key(label: str) -> Iterable[int]:
    return (
        tuple(
            int(part)
            for part in label.replace("-", ".").replace("_", ".").split(".")
            if part.isdigit()
        )
        or (0,)
    )


def _is_fw_platform(platform_id: str) -> bool:
    return platform_id.endswith("_FW")


class InMemoryStorage:
    """Simple store containing QA platforms, versions, runs, and sessions."""

    def __init__(self) -> None:
        self._platforms: Dict[str, PlatformModel] = {}
        self._versions: Dict[str, VersionModel] = {}
        self._runs: Dict[str, TestRunModel] = {}
        self._issues: Dict[str, TestIssueModel] = {}
        self._sessions: Dict[str, SessionModel] = {}
        self._seed()

    # ------------------------------------------------------------------
    # Platform helpers
    # ------------------------------------------------------------------
    def list_platforms(self, domain: DomainType) -> List[PlatformModel]:
        if domain == "FIRMWARE":
            return [p for p in self._platforms.values() if _is_fw_platform(p.id)]
        return [p for p in self._platforms.values() if not _is_fw_platform(p.id)]

    def add_platform(self, platform: PlatformModel) -> None:
        self._platforms[platform.id] = platform

    # ------------------------------------------------------------------
    # Version helpers
    # ------------------------------------------------------------------
    def list_versions(
        self,
        domain: DomainType,
        *,
        platform_id: Optional[str] = None,
        channel: Optional[Channel] = None,
    ) -> List[VersionModel]:
        versions = [v for v in self._versions.values() if v.domain == domain]
        if platform_id:
            versions = [v for v in versions if v.platform_id == platform_id]
        if channel:
            versions = [v for v in versions if v.release_channel == channel]
        return versions

    def add_version(self, version: VersionModel) -> VersionModel:
        self._validate_version_upgrade(version)
        if version.is_active:
            for existing in self._versions.values():
                if (
                    existing.domain == version.domain
                    and existing.platform_id == version.platform_id
                ):
                    existing.is_active = False
        self._versions[version.id] = version
        return version

    def _validate_version_upgrade(self, version: VersionModel) -> None:
        existing = [
            v
            for v in self._versions.values()
            if v.domain == version.domain
            and v.platform_id == version.platform_id
            and v.release_channel == version.release_channel
        ]
        if not existing:
            return
        latest = max(existing, key=lambda v: _version_key(v.version_label))
        if _version_key(version.version_label) < _version_key(latest.version_label):
            raise ValueError(
                "Version downgrade detected for platform"
                f" {version.platform_id} channel {version.release_channel or 'N/A'}"
            )

    # ------------------------------------------------------------------
    # Run helpers
    # ------------------------------------------------------------------
    def list_runs(
        self,
        domain: DomainType,
        *,
        platform_id: Optional[str] = None,
        version_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> List[TestRunModel]:
        runs = [r for r in self._runs.values() if r.domain == domain]
        if platform_id:
            runs = [r for r in runs if r.platform_id == platform_id]
        if version_id:
            runs = [r for r in runs if r.version_id == version_id]
        if session_id:
            runs = [r for r in runs if r.session_id == session_id]
        return runs

    def add_run(self, run: TestRunModel) -> TestRunModel:
        self._runs[run.id] = run
        return run

    # ------------------------------------------------------------------
    # Session helpers
    # ------------------------------------------------------------------
    def list_sessions(self) -> List[SessionModel]:
        return list(self._sessions.values())

    def get_session(self, session_id: str) -> Optional[SessionModel]:
        return self._sessions.get(session_id)

    def add_session(self, session: SessionModel) -> SessionModel:
        self._sessions[session.id] = session
        return session

    # ------------------------------------------------------------------
    def _seed(self) -> None:
        fw_platforms = [
            PlatformModel(id="S70PCI_FW", label="S70PCI", family="STB", vendor="Ventiva", model="S70PCI"),
            PlatformModel(id="JADE_FW", label="Jade", family="STB", vendor="Ventiva", model="Jade"),
            PlatformModel(id="SEI_X4_FW", label="SEI X4", family="STB", vendor="SEI", model="SEI X4"),
        ]
        app_platforms = [
            PlatformModel(id="ANDROID_TV_VSTB", label="Android TV vSTB", family="VSTB", vendor="Google"),
            PlatformModel(id="ANDROID_MOBILE", label="Android Mobile", family="MOBILE", vendor="Google"),
            PlatformModel(id="SMART_TV_LG", label="Smart TV LG", family="SMART_TV", vendor="LG"),
            PlatformModel(id="SMART_TV_SAMSUNG", label="Smart TV Samsung", family="SMART_TV", vendor="Samsung"),
            PlatformModel(id="APPLE_TV", label="Apple TV", family="APPLE_TV", vendor="Apple"),
            PlatformModel(id="IOS", label="iOS", family="IOS", vendor="Apple"),
        ]
        for platform in fw_platforms + app_platforms:
            self.add_platform(platform)

        now = datetime.utcnow()
        version_seed = [
            VersionModel(
                id="FW_3_5_0_SEI_X4",
                domain="FIRMWARE",
                platform_id="SEI_X4_FW",
                version_label="3.5.0",
                release_channel="QA",
                is_active=True,
            ),
            VersionModel(
                id="APP_25_3_303_ANDROID_TV_VSTB",
                domain="APP",
                platform_id="ANDROID_TV_VSTB",
                version_label="25.3.303",
                release_channel="QA",
                is_active=True,
            ),
        ]
        for version in version_seed:
            self.add_version(version)

        session = SessionModel(
            id="SESSION_FW_SEI_X4",
            domain="FIRMWARE",
            platform_id="SEI_X4_FW",
            version_id="FW_3_5_0_SEI_X4",
            tester_id="tester-01",
            status="RUNNING",
            created_at=now,
            updated_at=now,
        )
        self.add_session(session)

        run = TestRunModel(
            id="RUN_FW_SEI_X4_001",
            session_id=session.id,
            domain="FIRMWARE",
            platform_id=session.platform_id,
            version_id=session.version_id,
            tester_id=session.tester_id,
            status="RUNNING",
            pass_rate=0.0,
            passed_scenarios=0,
            failed_scenarios=0,
            total_scenarios=10,
            started_at=now,
        )
        self.add_run(run)

    def to_dict(self, obj) -> Dict:
        return asdict(obj)


storage = InMemoryStorage()


class QuickSetSessionStore:
    """Stores QuickSet scenario sessions in memory."""

    def __init__(self) -> None:
        self._sessions: Dict[str, QuickSetSessionModel] = {}
        self._lock = Lock()
        self._runtime: Dict[str, QuickSetRuntime] = {}

    def create_session(
        self,
        tester_id: str,
        stb_ip: str,
        scenario_name: str,
        steps: List[QuickSetStepModel],
    ) -> QuickSetSessionModel:
        session = QuickSetSessionModel(
            session_id=f"QS_{uuid4().hex[:8]}",
            tester_id=tester_id,
            stb_ip=stb_ip,
            scenario_name=scenario_name,
            start_time=datetime.utcnow(),
            steps=steps,
            result="pending",
            state="running",
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[QuickSetSessionModel]:
        with self._lock:
            return self._sessions.get(session_id)

    def upsert_step(self, session_id: str, step: QuickSetStepModel) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return
            for idx, existing in enumerate(session.steps):
                if existing.name == step.name:
                    session.steps[idx] = step
                    break
            else:
                session.steps.append(step)

    def set_status(self, session_id: str, status: str) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.result = status

    def set_state(self, session_id: str, state: str) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.state = state

    def set_pending_question(self, session_id: str, question: QuickSetQuestionModel) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.pending_question = question
                session.state = "awaiting_input"

    def clear_pending_question(self, session_id: str) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.pending_question = None
                if session.state != "completed":
                    session.state = "running"

    def complete_session(
        self,
        session_id: str,
        *,
        result: str,
        logs: Dict[str, str],
    ) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return
            session.result = result
            session.end_time = datetime.utcnow()
            session.logs.update(logs)
            session.state = "completed"
            session.pending_question = None

    def create_runtime(self, session_id: str) -> "QuickSetRuntime":
        runtime = QuickSetRuntime()
        self._runtime[session_id] = runtime
        return runtime

    def get_runtime(self, session_id: str) -> "QuickSetRuntime":
        runtime = self._runtime.get(session_id)
        if runtime is None:
            runtime = QuickSetRuntime()
            self._runtime[session_id] = runtime
        return runtime


@dataclass
class QuickSetRuntime:
    answer_event: Event = field(default_factory=Event)
    answer_value: Optional[str] = None


quickset_session_store = QuickSetSessionStore()
