from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from planner.models import Block
from .gemini import explain_block, explain_block_with_gemini


def explain_view(request, block_id):
    """
    JSON API endpoint that returns an AI/deterministic explanation for a scheduled block.

    GET /ai/explain/<block_id>/

    Query parameters:
        use_gemini (optional): Set to '1' to attempt Gemini API explanation.
                               Defaults to deterministic-only.

    Returns:
        JSON response with 'explanation', 'source', 'block_id', and 'score_breakdown'.
    """
    block = get_object_or_404(
        Block.objects.select_related('section', 'request', 'request__asset'),
        pk=block_id,
    )

    use_gemini = request.GET.get('use_gemini', '0') == '1'

    if use_gemini:
        result = explain_block_with_gemini(block)
    else:
        result = {
            'explanation': explain_block(block),
            'source': 'deterministic',
        }

    return JsonResponse({
        'block_id': block.id,
        'section': block.section.code,
        'asset': block.request.asset.name,
        'window': f"Day {block.day}, {block.start_hour:02d}:00 - {block.end_hour:02d}:00",
        'explanation': result['explanation'],
        'source': result['source'],
        'score_breakdown': block.score_breakdown,
    })
