from backend.config import Settings


def test_settings_are_limited_to_document_and_ai_runtime() -> None:
    fields = set(Settings.model_fields)
    expected = {
        "environment", "cors_origins", "max_upload_bytes", "max_upload_files", "max_total_upload_bytes", "max_pdf_pages",
        "workspace_ttl_minutes", "max_workspaces_in_memory", "bradesco_environment",
        "bradesco_identificador", "bradesco_senha", "bradesco_authorization_token", "bradesco_ca_bundle",
        "bradesco_text_url", "bradesco_identity_url", "bradesco_timeout_seconds", "bradesco_text_model",
        "bradesco_text_temperature", "bradesco_text_max_tokens", "bradesco_prompt_max_chars",
        "bradesco_analysis_max_tokens", "max_analysis_chunks", "bradesco_qa_url", "bradesco_qa_workflow_code", "gateway_token",
    }
    assert fields == expected
