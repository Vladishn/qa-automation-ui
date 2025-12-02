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
    QuickSetInfraCheck,
    QuickSetQuestion,
    QuickSetSession,
    QuickSetStep,
    SessionModel,
    TestIssueModel,
    TestRunModel,
    VersionModel,
)


@dataclass
class QuickSetRuntime:
    answer_event: Event = field(default_factory=Event)
    answer_value: Optional[str] = None


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
    """Thread-safe storage for QuickSet sessions and runtimes."""

    def __init__(self) -> None:
        self._sessions: Dict[str, QuickSetSession] = {}
        self._runtime: Dict[str, QuickSetRuntime] = {}
        self._lock = Lock()

    def _save(self, session_id: str, session: QuickSetSession) -> None:
        self._sessions[session_id] = session

    @staticmethod
    def _maybe_update_summary(session: QuickSetSession, step: QuickSetStep) -> QuickSetSession:
        if step.name == "analysis_summary":
            analysis = step.metadata.get("analysis")
            if isinstance(analysis, str):
                trimmed = analysis.strip()
                if trimmed:
                    return session.model_copy(update={"summary": trimmed})
        return session

    def create_session(self, tester_id: str, stb_ip: str, scenario_name: str) -> QuickSetSession:
        session_id = f"QS_{uuid4().hex[:8].upper()}"
        session = QuickSetSession(
            session_id=session_id,
            tester_id=tester_id,
            stb_ip=stb_ip,
            scenario_name=scenario_name,
            start_time=datetime.utcnow(),
            steps=[],
            logs={"adb": "", "logcat": ""},
            state="running",
        )
        with self._lock:
            self._save(session_id, session)
        return session.model_copy(deep=True)

    def get_session(self, session_id: str) -> Optional[QuickSetSession]:
        with self._lock:
            session = self._sessions.get(session_id)
            return session.model_copy(deep=True) if session else None

    def append_step(self, session_id: str, step: QuickSetStep) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return
            updated = session.model_copy(update={"steps": [*session.steps, step]})
            updated = self._maybe_update_summary(updated, step)
            self._save(session_id, updated)

    def replace_step(self, session_id: str, step_name: str, step: QuickSetStep) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return
            steps = list(session.steps)
            for idx, existing in enumerate(steps):
                if existing.name == step_name:
                    steps[idx] = step
                    break
            else:
                steps.append(step)
            updated = session.model_copy(update={"steps": steps})
            updated = self._maybe_update_summary(updated, step)
            self._save(session_id, updated)

    def set_state(self, session_id: str, state: str) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return
            updated = session.model_copy(update={"state": state})
            self._save(session_id, updated)

    def update_logs(self, session_id: str, logs: Dict[str, str]) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return
            new_logs = {**session.logs, **logs}
            updated = session.model_copy(update={"logs": new_logs})
            self._save(session_id, updated)

    def finalize_session(self, session_id: str, result: str, logs: Dict[str, str], summary: Optional[str] = None) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return
            update_payload = {
                "result": result,
                "end_time": datetime.utcnow(),
                "logs": {**session.logs, **logs},
                "state": "completed",
                "pending_question": None,
            }
            if summary:
                update_payload["summary"] = summary
            updated = session.model_copy(update=update_payload)
            self._save(session_id, updated)

    def set_tv_model(self, session_id: str, tv_model: Optional[str]) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return
            updated = session.model_copy(update={"tv_model": tv_model})
            self._save(session_id, updated)

    def set_remote_keys(self, session_id: str, keys: List[str]) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return
            updated = session.model_copy(update={"remote_keys": keys})
            self._save(session_id, updated)

    def add_infra_check(self, session_id: str, check: QuickSetInfraCheck) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return
            checks = list(session.infra_checks)
            for idx, existing in enumerate(checks):
                if existing.name == check.name:
                    checks[idx] = check
                    break
            else:
                checks.append(check)
            updated = session.model_copy(update={"infra_checks": checks})
            self._save(session_id, updated)

    def set_pending_question(self, session_id: str, question: QuickSetQuestion) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return
            updated = session.model_copy(update={"pending_question": question, "state": "awaiting_input"})
            self._save(session_id, updated)

    def clear_pending_question(self, session_id: str) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return
            new_state = session.state if session.state == "completed" else "running"
            updated = session.model_copy(update={"pending_question": None, "state": new_state})
            self._save(session_id, updated)

    def create_quickset_runtime(self, session_id: str) -> QuickSetRuntime:
        runtime = QuickSetRuntime()
        with self._lock:
            self._runtime[session_id] = runtime
        return runtime

    def get_quickset_runtime(self, session_id: str) -> QuickSetRuntime:
        runtime = self._runtime.get(session_id)
        if runtime is None:
            raise KeyError(f"Runtime for session {session_id} not found")
        return runtime

    def wait_for_answer(self, session_id: str, question: QuickSetQuestion) -> str:
        runtime = self.get_quickset_runtime(session_id)
        self.set_pending_question(session_id, question)
        runtime.answer_value = None
        runtime.answer_event.clear()
        runtime.answer_event.wait()
        answer = runtime.answer_value or ""
        self.clear_pending_question(session_id)
        return answer

    def deliver_answer(self, session_id: str, answer: str) -> None:
        runtime = self.get_quickset_runtime(session_id)
        runtime.answer_value = answer
        runtime.answer_event.set()


quickset_session_store = QuickSetSessionStore()
