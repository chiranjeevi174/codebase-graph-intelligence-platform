"""PR Comment Formatter module generating Markdown automated review reports."""

from app.pr.models import PRAnalysisResult


MARKER = "<!-- codebase-graph-intelligence-platform -->"


class PRCommentFormatter:
    """Formats a PRAnalysisResult into a concise, evidence-backed Markdown comment."""

    @classmethod
    def format_comment(cls, result: PRAnalysisResult) -> str:
        """Format PRAnalysisResult into Markdown with marker header."""
        summary = result.summary

        # Build Changed Symbols section
        sym_items = []
        for sym in result.changed_symbols[:10]:
            name = sym.get("symbol_name") or sym.get("qualified_name") or "Symbol"
            fpath = sym.get("file_path") or "unknown"
            chg_type = sym.get("change_type") or "MODIFIED"
            sym_items.append(f"- `{name}` in `{fpath}` ({chg_type})")
        sym_section = "\n".join(sym_items) if sym_items else "No structural symbol changes detected."

        # Build Signature Changes section
        sig_items = []
        for sig in result.signature_changes[:5]:
            sname = sig.get("symbol_name") or "Function"
            old_sig = sig.get("old_signature") or "N/A"
            new_sig = sig.get("new_signature") or "N/A"
            sig_items.append(f"- **{sname}**: `{old_sig}` → `{new_sig}`")
        sig_section = "\n".join(sig_items) if sig_items else "No signature changes detected."

        # Build API Changes section
        api_items = []
        for api in result.api_changes[:5]:
            path = api.get("path") or api.get("endpoint_id") or "API"
            method = api.get("http_method") or "GET"
            chg = api.get("change_type") or "MODIFIED"
            api_items.append(f"- `{method} {path}` ({chg})")
        api_section = "\n".join(api_items) if api_items else "No API contract changes detected."

        # Build Affected Components section
        aff_items = [f"- `{comp}`" for comp in result.affected_components[:10]]
        aff_section = "\n".join(aff_items) if aff_items else "No downstream components affected."

        # Build Cross Language Impact section
        cross_items = []
        for cl in result.cross_language_impacts[:5]:
            desc = cl.get("description") or cl.get("match_reason") or "Connected cross-language node"
            cross_items.append(f"- {desc}")
        cross_section = "\n".join(cross_items) if cross_items else "No cross-language API impacts identified."

        # Build Evidence section
        ev_items = []
        for ev in result.evidence[:5]:
            ev_items.append(f"- `{ev.file_path}:{ev.line_range}` [{ev.evidence_type}]: {ev.description or ev.symbol}")
        ev_section = "\n".join(ev_items) if ev_items else "Static graph traversal evidence compiled."

        val_status = "✅ Validated Evidence" if result.validation_status else "⚠️ Grounding Validation Review Suggested"

        return f"""{MARKER}
## Codebase Intelligence Analysis

### Change Summary
- **Changed Files:** {summary.changed_files_count}
- **Changed Symbols:** {summary.changed_symbols_count}
- **Signature Changes:** {summary.signature_changes_count}
- **API Changes:** {summary.api_changes_count}
- **Affected Files:** {summary.affected_files_count}
- **Cross-Language Impacts:** {summary.cross_language_impacts_count}

### Changed Symbols
{sym_section}

### Signature Changes
{sig_section}

### API Changes
{api_section}

### Potentially Affected Components
{aff_section}

### Cross-Language Impact
{cross_section}

### Explanation
{result.explanation or 'Static structural diff and impact analysis compiled.'}

### Evidence
{ev_section}

### Validation
{val_status}

### Analysis Metadata
- **Analysis Run:** {result.analysis_run_id}
- **Base SHA:** {result.base_sha}
- **Head SHA:** {result.head_sha}
"""

