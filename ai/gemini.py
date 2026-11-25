"""
AI explanation service for maintenance block scheduling decisions.

Provides deterministic rule-based explanations using block score_breakdown data.
Optionally integrates with Google Gemini API for enhanced natural language explanations,
with automatic fallback to deterministic explanations when API is unavailable.
"""

import hashlib
import json
import os
import logging

from planner.models import Block

logger = logging.getLogger(__name__)


def explain_block(block):
    """
    Generate a deterministic explanation of a scheduling decision using
    the block's score_breakdown data.

    This always works without any external API and provides the core explanation.

    Args:
        block: Block instance with score_breakdown JSON field.

    Returns:
        str: Human-readable explanation of why this block was scheduled at this time.
    """
    breakdown = block.score_breakdown or {}
    traffic = breakdown.get('traffic', block.cost)
    window = breakdown.get('window', f"Day {block.day}, {block.start_hour:02d}:00 - {block.end_hour:02d}:00")
    slots = breakdown.get('slots_considered', 'multiple')
    day_penalty = breakdown.get('day_penalty', 0)
    total_cost = breakdown.get('total', block.cost)
    avg_traffic = breakdown.get('avg_traffic_that_day', 'N/A')

    explanation = (
        f"Scheduled during {window} based on minimum traffic disruption. "
        f"Traffic density impact: {traffic} (average section density that day: {avg_traffic}). "
        f"Day penalty: {day_penalty}, total cost: {total_cost}. "
        f"Evaluated {slots} candidate time windows to find the optimal low-disruption slot."
    )

    duration = block.end_hour - block.start_hour
    if block.start_hour < 6:
        explanation += (
            f" The {duration}-hour block was placed during night hours "
            f"(low traffic period) to minimize impact on train operations."
        )
    elif traffic <= 3:
        explanation += (
            f" The selected window has very low traffic density, "
            f"making it ideal for the {duration}-hour maintenance activity."
        )

    return explanation


def explain_block_with_gemini(block):
    """
    Try to get an enhanced explanation from Google Gemini API.
    Falls back to deterministic explain_block() if the API is unavailable.

    Uses AICache to avoid redundant API calls.

    Args:
        block: Block instance with score_breakdown JSON field.

    Returns:
        dict: {'explanation': str, 'source': 'gemini' | 'deterministic'}
    """
    # Always compute deterministic fallback first
    deterministic = explain_block(block)

    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        return {'explanation': deterministic, 'source': 'deterministic'}

    # Check cache
    from ai.models import AICache
    cache_input = json.dumps({
        'block_id': block.id,
        'breakdown': block.score_breakdown,
        'day': block.day,
        'start_hour': block.start_hour,
        'end_hour': block.end_hour,
        'section': block.section.code,
        'asset': block.request.asset.name,
    }, sort_keys=True)
    cache_key = hashlib.sha256(cache_input.encode()).hexdigest()

    cached = AICache.objects.filter(key=cache_key).first()
    if cached:
        return {'explanation': cached.response, 'source': 'gemini (cached)'}

    # Attempt Gemini API call
    try:
        import google.generativeai as genai

        model_name = os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash')
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)

        breakdown = block.score_breakdown or {}
        prompt = (
            f"You are a railway maintenance scheduling assistant. Explain this scheduling decision "
            f"in 2-3 clear sentences for a railway operations manager:\n\n"
            f"- Section: {block.section.code} ({block.section.name})\n"
            f"- Asset: {block.request.asset.name} ({block.request.asset.get_asset_type_display()})\n"
            f"- Scheduled: Day {block.day}, {block.start_hour:02d}:00 to {block.end_hour:02d}:00\n"
            f"- Priority: P{block.request.priority}\n"
            f"- Traffic density impact: {breakdown.get('traffic', 'N/A')}\n"
            f"- Average section traffic that day: {breakdown.get('avg_traffic_that_day', 'N/A')}\n"
            f"- Candidate windows evaluated: {breakdown.get('slots_considered', 'N/A')}\n"
            f"- Total cost score: {breakdown.get('total', 'N/A')}\n\n"
            f"Explain why this time was optimal and what constraints were satisfied."
        )

        response = model.generate_content(prompt)
        explanation_text = response.text.strip()

        # Cache the response
        AICache.objects.create(key=cache_key, response=explanation_text)

        return {'explanation': explanation_text, 'source': 'gemini'}

    except Exception as e:
        logger.warning(f"Gemini API call failed for block #{block.id}: {e}")
        return {'explanation': deterministic, 'source': 'deterministic'}
