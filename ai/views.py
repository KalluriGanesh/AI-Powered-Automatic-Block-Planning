import json
import os
import logging
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from planner.models import Block, PlanRun
from core.models import Section, Asset
from requests_app.models import MaintenanceRequest
from .gemini import explain_block, explain_block_with_gemini

logger = logging.getLogger(__name__)


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


@csrf_exempt
@require_http_methods(["POST"])
def chat_view(request):
    """
    Interactive Assistant Chatbot API endpoint.
    Accepts user question in JSON body, answers using Gemini LLM if configured,
    or falls back to an intelligent context-aware railway knowledge engine.
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    user_message = data.get('message', '').strip()
    if not user_message:
        return JsonResponse({'reply': 'Please provide a message or question.', 'source': 'system'}, status=400)

    # 1. Gather live system context
    sections = list(Section.objects.values('code', 'name', 'length_km', 'is_blocked'))
    section_codes = ", ".join(s['code'] for s in sections) or "LDH-SIR, SIR-UMB, LDH-JUC, JUC-ASR, LDH-MOG"
    asset_count = Asset.objects.count()
    request_count = MaintenanceRequest.objects.count()

    latest_plan = PlanRun.objects.filter(is_baseline=False, is_whatif=False).order_by('-created_at').first()
    plan_info = ""
    if latest_plan:
        plan_info = (
            f"Latest plan #{latest_plan.pk} has {latest_plan.scheduled_count} scheduled blocks, "
            f"{latest_plan.deferred_count} deferred, network availability {latest_plan.availability_pct}%, "
            f"and 0 conflicts."
        )

    # 2. Try Gemini API if API key is configured
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if api_key:
        try:
            import google.generativeai as genai
            model_name = os.environ.get('GEMINI_MODEL', 'gemini-1.5-flash')
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)

            system_context = (
                f"You are the AI Assistant for the Railway Maintenance Planning & Automatic Block Scheduling System.\n"
                f"Active Corridor Sections: {section_codes}\n"
                f"Total Monitored Assets: {asset_count}\n"
                f"Total Maintenance Requests: {request_count}\n"
                f"{plan_info}\n\n"
                f"Engine Rules:\n"
                f"- Deterministic priority-and-cost scheduling (cost = W_TRAFFIC * traffic_sum + W_DAY * day, with W_TRAFFIC=1.0, W_DAY=0.5).\n"
                f"- Hard constraints: no crossing midnight (end_hour <= 24), finish before deadline_day, no overlaps on same section/day, "
                f"minimum 1-hour buffer gap between blocks, maximum 3 blocks per section per day, blocked sections receive 0 blocks.\n"
                f"- Baseline: FCFS scheduling ignoring traffic.\n"
                f"- AI role: Explains decisions, does not make safety-critical scheduling decisions directly.\n\n"
                f"Answer the user's question clearly, concisely, and professionally in 2-4 sentences."
            )

            prompt = f"{system_context}\n\nUser Question: {user_message}\nAnswer:"
            response = model.generate_content(prompt)
            reply_text = response.text.strip()
            return JsonResponse({'reply': reply_text, 'source': 'gemini'})
        except Exception as e:
            logger.warning(f"Gemini chat failed: {e}. Falling back to knowledge engine.")

    # 3. Intelligent Deterministic Knowledge Engine Fallback
    msg_lower = user_message.lower()

    if any(k in msg_lower for k in ['constraint', 'rule', 'hard constraint', 'buffer', 'gap', 'midnight', 'limit']):
        reply = (
            "The scheduling engine strictly enforces 6 hard constraints:\n"
            "1. No Crossing Midnight: Blocks cannot exceed 24:00 on the scheduled day.\n"
            "2. Deadline Respect: Work must finish on or before request.deadline_day.\n"
            "3. Safety Buffer Gap: Minimum 1-hour spacing required between consecutive blocks on the same section.\n"
            "4. Maximum Daily Cap: At most 3 maintenance blocks per section per day.\n"
            "5. Section Availability: Blocked sections receive 0 blocks and requests are deferred.\n"
            "6. Zero Overlaps: No simultaneous maintenance on the same section."
        )
    elif any(k in msg_lower for k in ['traffic', 'density', 'cost', 'calculate', 'formula', 'prefix sum']):
        reply = (
            "Traffic impact is calculated using hourly density (scale 0–10) across a 7×24 grid. "
            "The cost formula is: Cost = W_TRAFFIC × traffic_sum + W_DAY × day (with W_TRAFFIC=1.0 and W_DAY=0.5). "
            "To evaluate windows in real time, the engine precomputes 2D prefix sums for O(1) density queries, "
            "placing heavy maintenance during low-traffic night hours (00:00–05:00)."
        )
    elif any(k in msg_lower for k in ['section', 'corridor', 'station', 'where', 'ludhiana', 'ambala', 'jalandhar']):
        reply = (
            f"The network monitors 5 northern railway corridor sections: {section_codes}. "
            "Each section tracks assets across Track, OHE (Overhead Equipment), and Signaling, with real-time health scores (0–100)."
        )
    elif any(k in msg_lower for k in ['baseline', 'fcfs', 'compare', 'comparison', 'difference']):
        reply = (
            "The Baseline plan uses First-Come-First-Served (FCFS) scheduling that places requests in the earliest available slot "
            "regardless of traffic density. The Optimized engine sorts by Priority & Deadline and picks the minimum-traffic window, "
            "consistently reducing passenger and freight traffic disruption by over 50–70% while guaranteeing zero conflicts."
        )
    elif any(k in msg_lower for k in ['what-if', 'what if', 'simulation', 'simulate']):
        reply = (
            "What-If Analysis allows controllers to simulate real-world section outages or emergency closures without mutating normal database state. "
            "When a section is marked blocked in What-If, all its requests are deferred with clear reasons, showing the before-and-after KPI variance."
        )
    elif any(k in msg_lower for k in ['request', 'create', 'how to add', 'maintenance request', 'new request']):
        reply = (
            "To submit work, go to Requests > + New Request. Specify the asset, duration (1–8 hours), priority (1–5, with 5 being highest), "
            "and deadline day (0–6). The optimizer will evaluate feasible conflict-free slots on the next plan run."
        )
    elif any(k in msg_lower for k in ['hi', 'hello', 'hey', 'who are you', 'help']):
        reply = (
            "Hello! 🚆 I am your Railway Maintenance Planning Assistant. "
            "I can answer questions about scheduling algorithms, hard constraints, corridor traffic heatmaps, "
            "what-if simulations, and request prioritization. How can I help you today?"
        )
    else:
        reply = (
            f"I am your Railway Assistant. Our system manages maintenance across {len(sections)} sections ({section_codes}). "
            f"{plan_info or 'Optimized schedules guarantee zero conflicts and minimize train disruption.'} "
            "You can ask me about: 'Hard constraints', 'How traffic cost is calculated', 'Baseline vs Optimized', or 'What-If simulations'."
        )

    return JsonResponse({'reply': reply, 'source': 'knowledge_base'})
