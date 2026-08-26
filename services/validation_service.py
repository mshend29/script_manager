from __future__ import annotations

from dataclasses import dataclass

from core.database import Database, SCHEMA_VERSION
from services.review_service import NON_DIALOGUE


SYSTEM = "SYSTEM"
REVIEW = "REVIEW"
WORKFLOW = "WORKFLOW"

ERROR = "ERROR"
WARNING = "WARNING"

ACTION_REVIEW = "REVIEW"
ACTION_SOURCES = "SOURCES"
ACTION_TRACKING = "TRACKING"


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    category: str
    code: str
    message: str
    episode_number: int | None = None
    entity: str = ""
    action: str = ""
    dialogue_id: int | None = None
    character_id: int | None = None
    talent_id: int | None = None
    source_file_path: str = ""


@dataclass(frozen=True)
class ValidationSummary:
    system_errors: int
    needs_review: int
    workflow_warnings: int


class ValidationService:
    def __init__(self, database: Database):
        self.database = database

    def summarize(self, issues: list[ValidationIssue]) -> ValidationSummary:
        return ValidationSummary(
            system_errors=sum(
                1
                for issue in issues
                if issue.category == SYSTEM and issue.severity == ERROR
            ),
            needs_review=sum(1 for issue in issues if issue.category == REVIEW),
            workflow_warnings=sum(
                1 for issue in issues if issue.category == WORKFLOW
            ),
        )

    def validate(self) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        with self.database.connect() as connection:
            schema_row = connection.execute(
                "SELECT value FROM app_meta WHERE key = 'schema_version'"
            ).fetchone()
            schema_value = str(schema_row["value"] if schema_row else "")
            if schema_value != str(SCHEMA_VERSION):
                issues.append(
                    ValidationIssue(
                        severity=ERROR,
                        category=SYSTEM,
                        code="SCHEMA_VERSION",
                        entity="Database",
                        message=(
                            f"Database schema {schema_value or '?'} != aplikasi "
                            f"{SCHEMA_VERSION}."
                        ),
                    )
                )

            for row in connection.execute("PRAGMA foreign_key_check").fetchall():
                issues.append(
                    ValidationIssue(
                        severity=ERROR,
                        category=SYSTEM,
                        code="FOREIGN_KEY",
                        entity=str(row[0]),
                        message=(
                            f"Foreign key invalid pada tabel {row[0]}, "
                            f"rowid {row[1]}."
                        ),
                    )
                )

            missing_character_rows = connection.execute(
                """
                SELECT
                    d.id AS dialogue_id,
                    e.episode_number,
                    d.dialog_text,
                    COALESCE(sf.file_path, '') AS source_file_path
                FROM dialogues AS d
                JOIN episodes AS e ON e.id = d.episode_id
                LEFT JOIN source_files AS sf ON sf.id = d.source_file_id
                WHERE d.is_active = 1
                  AND e.is_active = 1
                  AND NOT EXISTS (
                      SELECT 1
                      FROM dialog_cast AS dc
                      WHERE dc.dialogue_id = d.id
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM dialogue_review AS dr
                      WHERE dr.dialogue_id = d.id
                        AND dr.classification = ?
                  )
                ORDER BY e.episode_number, d.source_row, d.id
                """,
                (NON_DIALOGUE,),
            ).fetchall()
            for row in missing_character_rows:
                issues.append(
                    ValidationIssue(
                        severity=WARNING,
                        category=REVIEW,
                        code="MISSING_CHARACTER",
                        episode_number=int(row["episode_number"]),
                        entity="Character Unknown",
                        message=str(row["dialog_text"]),
                        action=ACTION_REVIEW,
                        dialogue_id=int(row["dialogue_id"]),
                        source_file_path=str(row["source_file_path"] or ""),
                    )
                )

            missing_talent_rows = connection.execute(
                """
                SELECT
                    d.id AS dialogue_id,
                    e.episode_number,
                    c.id AS character_id,
                    c.name AS character_name,
                    d.dialog_text,
                    COALESCE(sf.file_path, '') AS source_file_path
                FROM dialog_cast AS dc
                JOIN dialogues AS d ON d.id = dc.dialogue_id
                JOIN episodes AS e ON e.id = d.episode_id
                JOIN characters AS c ON c.id = dc.character_id
                LEFT JOIN source_files AS sf ON sf.id = d.source_file_id
                WHERE d.is_active = 1
                  AND e.is_active = 1
                  AND c.is_active = 1
                  AND dc.talent_id IS NULL
                ORDER BY e.episode_number, d.source_row, d.id, dc.position
                """
            ).fetchall()
            for row in missing_talent_rows:
                issues.append(
                    ValidationIssue(
                        severity=WARNING,
                        category=REVIEW,
                        code="MISSING_TALENT",
                        episode_number=int(row["episode_number"]),
                        entity=str(row["character_name"]),
                        message=str(row["dialog_text"]),
                        action=ACTION_REVIEW,
                        dialogue_id=int(row["dialogue_id"]),
                        character_id=int(row["character_id"]),
                        source_file_path=str(row["source_file_path"] or ""),
                    )
                )

            duplicate_sources = connection.execute(
                """
                SELECT episode_number, COUNT(*) AS total
                FROM source_files
                WHERE is_active = 1 AND episode_number IS NOT NULL
                GROUP BY episode_number
                HAVING COUNT(*) > 1
                ORDER BY episode_number
                """
            ).fetchall()
            for row in duplicate_sources:
                episode_number = int(row["episode_number"])
                issues.append(
                    ValidationIssue(
                        severity=ERROR,
                        category=SYSTEM,
                        code="DUPLICATE_SOURCE_EPISODE",
                        episode_number=episode_number,
                        entity=f"Episode {episode_number}",
                        message=(
                            f"Episode {episode_number} memiliki "
                            f"{int(row['total'])} source aktif."
                        ),
                        action=ACTION_SOURCES,
                    )
                )

            invalid_dialogues = connection.execute(
                """
                SELECT d.id, e.episode_number, d.dialog_text
                FROM dialogues AS d
                JOIN episodes AS e ON e.id = d.episode_id
                WHERE d.is_active = 1 AND e.is_active = 0
                ORDER BY e.episode_number, d.id
                """
            ).fetchall()
            for row in invalid_dialogues:
                issues.append(
                    ValidationIssue(
                        severity=ERROR,
                        category=SYSTEM,
                        code="ACTIVE_DIALOGUE_INACTIVE_EPISODE",
                        episode_number=int(row["episode_number"]),
                        entity="Dialogue",
                        message=str(row["dialog_text"]),
                        dialogue_id=int(row["id"]),
                    )
                )

            inactive_source_episodes = connection.execute(
                """
                SELECT e.episode_number
                FROM episodes AS e
                JOIN source_files AS sf ON sf.id = e.source_file_id
                WHERE e.is_active = 1 AND sf.is_active = 0
                ORDER BY e.episode_number
                """
            ).fetchall()
            for row in inactive_source_episodes:
                episode_number = int(row["episode_number"])
                issues.append(
                    ValidationIssue(
                        severity=ERROR,
                        category=SYSTEM,
                        code="ACTIVE_EPISODE_INACTIVE_SOURCE",
                        episode_number=episode_number,
                        entity=f"Episode {episode_number}",
                        message="Episode aktif menunjuk source file yang inactive.",
                        action=ACTION_SOURCES,
                    )
                )

            empty_active_episodes = connection.execute(
                """
                SELECT e.episode_number
                FROM episodes AS e
                JOIN source_files AS sf ON sf.id = e.source_file_id
                WHERE e.is_active = 1
                  AND sf.is_active = 1
                  AND EXISTS (
                      SELECT 1
                      FROM dialogues AS history
                      WHERE history.episode_id = e.id
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM dialogues AS active_dialogue
                      WHERE active_dialogue.episode_id = e.id
                        AND active_dialogue.is_active = 1
                  )
                ORDER BY e.episode_number
                """
            ).fetchall()
            for row in empty_active_episodes:
                episode_number = int(row["episode_number"])
                issues.append(
                    ValidationIssue(
                        severity=ERROR,
                        category=SYSTEM,
                        code="ACTIVE_EPISODE_WITHOUT_ACTIVE_DIALOGUES",
                        episode_number=episode_number,
                        entity=f"Episode {episode_number}",
                        message="Episode/source aktif hanya memiliki dialogue inactive.",
                        action=ACTION_SOURCES,
                    )
                )

            inactive_cast = connection.execute(
                """
                SELECT
                    d.id AS dialogue_id,
                    e.episode_number,
                    c.id AS character_id,
                    c.name AS character_name,
                    dc.talent_id,
                    COALESCE(t.name, '') AS talent_name,
                    c.is_active AS character_active,
                    t.is_active AS talent_active
                FROM dialog_cast AS dc
                JOIN dialogues AS d ON d.id = dc.dialogue_id
                JOIN episodes AS e ON e.id = d.episode_id
                JOIN characters AS c ON c.id = dc.character_id
                LEFT JOIN talents AS t ON t.id = dc.talent_id
                WHERE d.is_active = 1
                  AND (
                      c.is_active = 0
                      OR (
                          dc.talent_id IS NOT NULL
                          AND COALESCE(t.is_active, 0) = 0
                      )
                  )
                ORDER BY e.episode_number, d.id
                """
            ).fetchall()
            for row in inactive_cast:
                talent_text = str(row["talent_name"] or "Talent Unknown")
                issues.append(
                    ValidationIssue(
                        severity=ERROR,
                        category=SYSTEM,
                        code="INACTIVE_CAST_ENTITY",
                        episode_number=int(row["episode_number"]),
                        entity=str(row["character_name"]),
                        message=(
                            "Cast aktif menunjuk character/talent inactive: "
                            f"{row['character_name']} / {talent_text}."
                        ),
                        dialogue_id=int(row["dialogue_id"]),
                        character_id=int(row["character_id"]),
                        talent_id=(
                            int(row["talent_id"])
                            if row["talent_id"] is not None
                            else None
                        ),
                    )
                )

            downstream_rows = connection.execute(
                """
                SELECT
                    ss.episode_id,
                    e.episode_number,
                    ss.talent_id,
                    t.name AS talent_name,
                    ss.character_id,
                    c.name AS character_name,
                    ss.status
                FROM stem_status AS ss
                JOIN episodes AS e ON e.id = ss.episode_id
                JOIN talents AS t ON t.id = ss.talent_id
                JOIN characters AS c ON c.id = ss.character_id
                WHERE ss.status IN ('READY_TO_STEM', 'STEMMED', 'DELIVERED')
                  AND EXISTS (
                      SELECT 1
                      FROM dialogues AS d
                      JOIN dialog_cast AS dc ON dc.dialogue_id = d.id
                      LEFT JOIN recording_status AS rs ON rs.dialogue_id = d.id
                      WHERE d.episode_id = ss.episode_id
                        AND dc.talent_id = ss.talent_id
                        AND dc.character_id = ss.character_id
                        AND d.is_active = 1
                        AND COALESCE(rs.is_recorded, 0) = 0
                  )
                ORDER BY e.episode_number, t.name, c.name
                """
            ).fetchall()
            for row in downstream_rows:
                issues.append(
                    ValidationIssue(
                        severity=WARNING,
                        category=WORKFLOW,
                        code="DOWNSTREAM_BEFORE_RECORDED",
                        episode_number=int(row["episode_number"]),
                        entity=(
                            f"{row['character_name']} / {row['talent_name']}"
                        ),
                        message=(
                            f"Status {row['status']} tersimpan sementara recording "
                            "belum lengkap."
                        ),
                        action=ACTION_TRACKING,
                        character_id=int(row["character_id"]),
                        talent_id=int(row["talent_id"]),
                    )
                )

        category_order = {SYSTEM: 0, REVIEW: 1, WORKFLOW: 2}
        severity_order = {ERROR: 0, WARNING: 1}
        issues.sort(
            key=lambda issue: (
                category_order.get(issue.category, 99),
                severity_order.get(issue.severity, 99),
                issue.episode_number if issue.episode_number is not None else -1,
                issue.code,
                issue.entity.casefold(),
            )
        )
        return issues
