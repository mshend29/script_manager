from __future__ import annotations

from services.validation_service import (
    ACTION_TRACKING,
    ERROR,
    SYSTEM,
    WARNING,
    WORKFLOW,
    ValidationIssue,
    ValidationService,
)


class AliasValidationService(ValidationService):
    """Extend the established validator with character-alias integrity."""

    def validate(self) -> list[ValidationIssue]:
        # Replace the legacy downstream check because tracking is now scoped to
        # canonical character identity rather than the raw source character id.
        issues = [
            issue
            for issue in super().validate()
            if issue.code != "DOWNSTREAM_BEFORE_RECORDED"
        ]

        with self.database.connect() as connection:
            alias_rows = connection.execute(
                """
                SELECT
                    ca.id,
                    ca.alias_name,
                    ca.normalized_alias,
                    ca.source_character_id,
                    source.name AS source_name,
                    source.normalized_name AS source_normalized,
                    source.is_active AS source_active,
                    ca.canonical_character_id,
                    canonical.name AS canonical_name,
                    canonical.is_active AS canonical_active,
                    CASE WHEN target_alias.id IS NULL THEN 0 ELSE 1 END AS target_is_alias,
                    CASE WHEN child_alias.id IS NULL THEN 0 ELSE 1 END AS source_owns_alias
                FROM character_alias AS ca
                JOIN characters AS source ON source.id = ca.source_character_id
                JOIN characters AS canonical ON canonical.id = ca.canonical_character_id
                LEFT JOIN character_alias AS target_alias
                  ON target_alias.source_character_id = ca.canonical_character_id
                LEFT JOIN character_alias AS child_alias
                  ON child_alias.canonical_character_id = ca.source_character_id
                ORDER BY ca.id
                """
            ).fetchall()

            seen_codes: set[tuple[str, int]] = set()
            for row in alias_rows:
                alias_id = int(row["id"])
                label = f"{row['source_name']} → {row['canonical_name']}"

                def add(code: str, message: str) -> None:
                    key = (code, alias_id)
                    if key in seen_codes:
                        return
                    seen_codes.add(key)
                    issues.append(
                        ValidationIssue(
                            severity=ERROR,
                            category=SYSTEM,
                            code=code,
                            entity=label,
                            message=message,
                            character_id=int(row["canonical_character_id"]),
                        )
                    )

                if int(row["source_active"] or 0) != 1:
                    add(
                        "ALIAS_SOURCE_INACTIVE",
                        "Source character untuk alias sudah inactive.",
                    )
                if int(row["canonical_active"] or 0) != 1:
                    add(
                        "ALIAS_TARGET_INACTIVE",
                        "Canonical character untuk alias sudah inactive.",
                    )
                if int(row["target_is_alias"] or 0):
                    add(
                        "ALIAS_CHAIN",
                        "Alias menunjuk ke character yang juga merupakan alias.",
                    )
                if int(row["source_owns_alias"] or 0):
                    add(
                        "ALIAS_CHAIN",
                        "Character yang menjadi alias masih memiliki alias lain.",
                    )
                if str(row["normalized_alias"]) != str(row["source_normalized"]):
                    add(
                        "ALIAS_NAME_MISMATCH",
                        "Nama alias tidak lagi sama dengan normalized source character.",
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
                      LEFT JOIN character_alias AS ca
                        ON ca.source_character_id = dc.character_id
                      LEFT JOIN recording_status AS rs ON rs.dialogue_id = d.id
                      WHERE d.episode_id = ss.episode_id
                        AND dc.talent_id = ss.talent_id
                        AND COALESCE(ca.canonical_character_id, dc.character_id)
                            = ss.character_id
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
                        entity=f"{row['character_name']} / {row['talent_name']}",
                        message=(
                            f"Status {row['status']} tersimpan sementara recording "
                            "belum lengkap."
                        ),
                        action=ACTION_TRACKING,
                        character_id=int(row["character_id"]),
                        talent_id=int(row["talent_id"]),
                    )
                )

        category_order = {SYSTEM: 0, "REVIEW": 1, WORKFLOW: 2}
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
