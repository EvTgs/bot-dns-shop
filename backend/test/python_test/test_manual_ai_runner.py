import json

from app.ai_orchestrator import NormalizedSearchRequest
from app.manual_ai_runner import (
    MANUAL_STAGE_ORDER,
    build_manual_filters_payload,
    build_manual_response_template,
)


def test_manual_stage_order_matches_expected_pipeline() -> None:
    assert MANUAL_STAGE_ORDER == (
        "normalize",
        "category_resolve",
        "filters_map",
        "filters_select",
        "parser",
        "shortlist",
        "details",
        "final_analysis",
    )


def test_build_manual_response_template_for_normalize_contains_required_format() -> None:
    template = build_manual_response_template("normalize")

    assert '"product_type"' in template
    assert '"ranking_policy"' in template
    assert '"price_band_hint"' in template
    assert '"soft_wishes"' in template


def test_build_manual_response_template_for_filters_select_contains_json_shape() -> None:
    template = build_manual_response_template("filters_select")

    assert '"filters"' in template
    assert '"values"' in template


def test_build_manual_response_template_for_shortlist_contains_selected_urls_shape() -> None:
    template = build_manual_response_template("shortlist")

    assert '"selected_urls"' in template


def test_build_manual_response_template_for_final_analysis_contains_three_blocks() -> None:
    template = build_manual_response_template("final_analysis")

    assert "Лучший вариант" in template
    assert "Почему он подходит" in template
    assert "Что сильнее у альтернатив" in template
    assert "Компромиссы и проверки" in template


def test_build_manual_filters_payload_sends_only_patch_context_for_problematic_constraints() -> None:
    payload = build_manual_filters_payload(
        question="Найди монитор IPS",
        history=[],
        section_url="https://dns.example/search?q=монитор&category=cat",
        normalized_request=NormalizedSearchRequest(
            product_type="monitor",
            query="монитор",
            price_min=17500,
            price_max=36750,
            wishes=("ips",),
        ),
        preselected_filters=[],
        coverage=[
            {"constraint_key": "matrix_type", "status": "covered", "confidence": 0.95},
            {"constraint_key": "refresh_rate", "status": "uncovered", "confidence": 0.0},
        ],
        candidate_packets=[
            {"constraint": {"key": "matrix_type"}, "candidate_filters": [{"id": "f[ok]"}]},
            {"constraint": {"key": "refresh_rate"}, "candidate_filters": [{"id": "f[hz]"}]},
        ],
    )
    data = json.loads(payload)

    assert data["task"] == "filters_patch"
    assert "filters_map" not in data
    assert len(data["coverage"]) == 2
    assert len(data["candidate_packets"]) == 1
    assert data["candidate_packets"][0]["constraint"]["key"] == "refresh_rate"
