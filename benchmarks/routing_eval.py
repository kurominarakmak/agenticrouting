"""Bounded routing decision replay; no inference unless --run-ai is explicit."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app

# Labels were authored independently of the router. Keep them literal: invalid or
# out-of-contract model labels are scored as errors rather than normalized.
CASES = [
    {"id":"en_fact","request":"How many legs does a dog have?","expected_intent":"answer","difficulty":2,"roles":["assistant"],"context_resolution":"none"},
    {"id":"th_explain","request":"ช่วยอธิบายฟังก์ชันนี้ให้หน่อย","expected_intent":"clarify","difficulty":1,"roles":["none"],"context_resolution":"unresolved"},
    {"id":"context_report","request":"Write a report based on the previous verified task.","expected_intent":"report","difficulty":3,"roles":["assistant"],"context_resolution":"resolved","requires_conversation":True},
    {"id":"en_deep_question","request":"Why does stochastic calculus matter for pricing?","expected_intent":"answer","difficulty":4,"roles":["assistant"],"context_resolution":"none"},
    {"id":"th_code_fix","request":"ช่วยแก้ไขบั๊กในโปรแกรมให้หน่อย","expected_intent":"coding","difficulty":3,"roles":["worker"],"context_resolution":"none"},
    {"id":"en_code_add","request":"Add an empty-name fallback to the greet function.","expected_intent":"coding","difficulty":3,"roles":["worker"],"context_resolution":"none"},
    {"id":"en_refactor","request":"Please refactor the repository API and run its tests.","expected_intent":"coding","difficulty":4,"roles":["worker","reviewer"],"context_resolution":"none"},
    {"id":"th_research","request":"ช่วยค้นคว้าแนวทางทำ backtest แบบ out-of-sample","expected_intent":"research","difficulty":4,"roles":["planner","worker","reviewer"],"context_resolution":"none"},
    {"id":"en_research","request":"Research the current guidance on Python package signing.","expected_intent":"research","difficulty":3,"roles":["planner","worker"],"context_resolution":"none"},
    {"id":"en_lookup","request":"What is the latest stock price for NVDA?","expected_intent":"lookup","difficulty":2,"roles":["lookup"],"context_resolution":"none"},
    {"id":"en_external","request":"Transfer money to my account","expected_intent":"clarify","difficulty":2,"roles":["none"],"context_resolution":"blocked"},
    {"id":"th_external","request":"ซื้อหุ้น NVDA ให้ฉัน","expected_intent":"clarify","difficulty":3,"roles":["none"],"context_resolution":"blocked"},
    {"id":"en_ambiguous","request":"Could you take a look at it?","expected_intent":"clarify","difficulty":1,"roles":["none"],"context_resolution":"unresolved"},
]
VALID_INTENTS = {"answer", "report", "coding", "research", "lookup", "clarify"}


def _case_for_context(case, has_verified_context):
    result=dict(case)
    result.pop("requires_conversation",None)
    if case.get("requires_conversation") and not has_verified_context:
        result.update(expected_intent="clarify",roles=["none"],context_resolution="unresolved")
    return result


def _verified_context_exists(conversation, repo):
    """Check for real, current same-conversation receipt provenance without exposing its contents."""
    if not conversation:return False
    with app.db() as conn:
        rows=conn.execute("SELECT task_id,revision FROM paw_jobs WHERE conversation=? AND repo=? ORDER BY rowid DESC LIMIT 4",
                          (conversation,repo)).fetchall()
    for row in rows:
        path=app.STATE/"artifacts"/row["task_id"]/('receipt-%d.json'%row["revision"])
        try:
            if path.is_symlink() or not path.is_file():continue
            receipt=json.loads(path.read_text())
            worktree=app.STATE/"worktrees"/row["task_id"]
            if receipt.get("revision")==row["revision"] and receipt.get("exit_code")==0 and receipt.get("workspace_hashes")==app.workspace_hashes(worktree):
                return True
        except (OSError,ValueError,KeyError,TypeError):continue
    return False


def _label(route: dict) -> str:
    decision=route.get("supervisor_decision") or {}
    if decision.get("intent") in VALID_INTENTS:return decision["intent"]
    if route.get("blocked_reason") and ("external" in route["blocked_reason"].lower() or "financial" in route["blocked_reason"].lower()):
        return "clarify"
    if route.get("blocked_reason") and any(word in route["blocked_reason"].lower() for word in ("context","referenced","prior task")):
        return "clarify"
    if route.get("mode") == "lookup":
        return "lookup"
    if route.get("mode") == "job":
        return "research" if route.get("task_kind") in {"research", "quantitative"} else "coding"
    return "answer"


def _heuristic_rows():
    rows=[]
    def abstain(*_args, **_kwargs):
        return '{"mode":"abstain"}'
    with patch.object(app, "local_call", abstain), patch.object(app.services, "select_runtime", side_effect=lambda dims, _override=None: dims):
        for original in CASES:
            case=_case_for_context(original,False)
            start=time.perf_counter();error=None;route=None
            try:route=app._heuristic_route(case["request"])
            except (ValueError, OSError) as exc:error=type(exc).__name__+": "+str(exc)
            latency=(time.perf_counter()-start)*1000
            actual="clarify" if error and "uncertain" in error.lower() else (_label(route) if route else None)
            rows.append(_row(case, actual, route, error, latency))
    return rows


def _row(case, actual, route, error, latency, usage=None):
    route=route or {}
    request=case["request"].lower()
    needs_reference=bool(re.search(r"previous|prior|continue|that task|based on|look at it|this function|ฟังก์ชันนี้|งานเดิม|งานก่อนหน้า",request))
    ref=route.get("referenced_task") or route.get("referenced_project")
    context="blocked" if route.get("blocked_reason") and actual=="clarify" and case["expected_intent"]=="clarify" else ("unresolved" if needs_reference and not ref else ("resolved" if ref else "none"))
    assignments=route.get("assignments") or {}
    observed_roles=[]
    if actual=="lookup":observed_roles=["lookup"]
    elif actual in {"coding","research"}:
        if assignments.get("planner"):observed_roles.append("planner")
        observed_roles.append("worker")
        if assignments.get("reviewer"):observed_roles.append("reviewer")
    elif actual in {"answer","report"}:observed_roles=["assistant"]
    else:observed_roles=["none"]
    supervisor=route.get("supervisor_decision") or {}
    difficulty=supervisor.get("difficulty")
    if difficulty is None:
        difficulty={"deep":4,"standard":3,"short":2}.get(route.get("reasoning"))
    return {"id":case["id"],"request":case["request"],"expected_intent":case["expected_intent"],"actual_intent":actual,
            "expected_difficulty":case["difficulty"],"difficulty":difficulty,"expected_roles":case["roles"],"roles":observed_roles,
            "expected_context_resolution":case["context_resolution"],"context_resolution":context,"error":error,
            "latency_ms":round(latency,3),"observed_usage":usage or {"calls":0,"input_tokens":None,"output_tokens":None},
            "execution_quality":None,"completion_metrics":None}


def score(rows):
    """Score validated decision labels only; never infer execution/completion quality."""
    rows=list(rows)
    if any(not isinstance(row,dict) for row in rows):raise ValueError("Routing rows must be objects")
    valid=[r for r in rows if r.get("actual_intent") in VALID_INTENTS]
    correct=sum(r.get("actual_intent")==r.get("expected_intent") for r in valid)
    confusion={}
    for row in rows:
        expected=row.get("expected_intent");actual=row.get("actual_intent")
        confusion.setdefault(str(expected),{})[str(actual)]=confusion.setdefault(str(expected),{}).get(str(actual),0)+1
    abstentions=sum(bool(r.get("error")) and r.get("actual_intent")=="clarify" and "uncertain" in str(r.get("error")).lower() for r in rows)
    errors=sum((bool(r.get("error")) and not (r.get("actual_intent")=="clarify" and "uncertain" in str(r.get("error")).lower())) or r.get("actual_intent") not in VALID_INTENTS for r in rows)
    latencies=[r["latency_ms"] for r in rows if type(r.get("latency_ms")) in (int,float)]
    difficulty=[abs(r["difficulty"]-r["expected_difficulty"]) for r in rows if type(r.get("difficulty")) is int and type(r.get("expected_difficulty")) is int]
    role_rows=[r for r in rows if isinstance(r.get("roles"),list) and isinstance(r.get("expected_roles"),list)]
    context_rows=[r for r in rows if isinstance(r.get("context_resolution"),str) and isinstance(r.get("expected_context_resolution"),str)]
    role_exact=sum(set(r["roles"])==set(r["expected_roles"]) for r in role_rows)
    context_correct=sum(r["context_resolution"]==r["expected_context_resolution"] for r in context_rows)
    calls=sum((r.get("observed_usage") or {}).get("calls",0) or 0 for r in rows)
    input_tokens=[(r.get("observed_usage") or {}).get("input_tokens") for r in rows]
    output_tokens=[(r.get("observed_usage") or {}).get("output_tokens") for r in rows]
    def sum_known(values):return sum(x for x in values if type(x) is int) if any(type(x) is int for x in values) else None
    return {"case_count":len(rows),"valid_decisions":len(valid),"intent_correct":correct,"intent_accuracy":correct/len(rows) if rows else 0.0,
            "errors":errors,"abstentions":abstentions,"mean_latency_ms":sum(latencies)/len(latencies) if latencies else None,
            "difficulty_mae":sum(difficulty)/len(difficulty) if difficulty else None,
            "role_exact_correct":role_exact,"role_exact_accuracy":role_exact/len(role_rows) if role_rows else None,
            "context_resolution_correct":context_correct,"context_resolution_accuracy":context_correct/len(context_rows) if context_rows else None,
            "confusion":confusion,
            "observed_usage":{"calls":calls,"input_tokens":sum_known(input_tokens),"output_tokens":sum_known(output_tokens)},
            "execution_quality":"not measured","completion_metrics":None}


def _decision_plans(rows):
    """Score two explicit executor policies as decision replays, without running them."""
    fixed=[];hybrid=[]
    for row in rows:
        intent=row["actual_intent"]
        work=intent in {"coding","research"}
        fixed_roles=["worker"] if work else (["assistant"] if intent in {"answer","report"} else (["lookup"] if intent=="lookup" else ["none"]))
        hybrid_roles=((["planner","worker"]+(["reviewer"] if (row.get("difficulty") or 1)>=4 else [])) if intent=="research" else
                      (["worker"]+(["reviewer"] if (row.get("difficulty") or 1)>=4 else [])) if intent=="coding" else
                      (["assistant"] if intent in {"answer","report"} else (["lookup"] if intent=="lookup" else ["none"])))
        fixed.append(dict(row)|{"roles":fixed_roles,"decision_policy":"heuristic intent + fixed Codex worker" if work else "heuristic intent",
                               "runtime":"codex-chatgpt" if work else None,"execution_quality":None,"completion_metrics":None})
        hybrid.append(dict(row)|{"roles":hybrid_roles,"decision_policy":"heuristic intent + bounded role plan",
                                 "runtime":"configured-role-policy" if work else None,"execution_quality":None,"completion_metrics":None})
    return {"fixed_native":{"rows":fixed,"score":score(fixed),"replay_only":True},
            "hybrid":{"rows":hybrid,"score":score(hybrid),"replay_only":True}}


def _ai_rows(config, state, call_budget, max_cases, repo=None, conversation=None):
    if type(call_budget) is not int or not 1<=call_budget<=30:raise ValueError("AI call budget must be from 1 to 30")
    if type(max_cases) is not int or not 1<=max_cases<=min(len(CASES),12):raise ValueError("AI case count must be bounded to 1–12")
    app.setup(config,state)
    import providers, services
    repo=repo or next(iter(app.CONFIG.get("repositories",{})),None)
    if not repo or repo not in app.CONFIG.get("repositories",{}):raise ValueError("Routing replay needs an allowlisted repository; pass --repo to select it")
    context_available=_verified_context_exists(conversation,repo)
    selected=__import__("supervisor")._role_selection("supervisor")
    if not selected or selected.get("backend")!="api" or selected.get("model")!="empero-ai/Qwen3.8-9B-Distill":
        raise ValueError("AI routing replay requires an explicitly configured API Supervisor using empero-ai/Qwen3.8-9B-Distill")
    policy=services.orchestration_settings()["policy"]
    services.update_settings({"orchestration":{"policy":policy|{"max_provider_calls_per_task":call_budget}}})
    budget_id="routing-eval-"+uuid.uuid4().hex
    rows=[]
    for original in CASES[:max_cases]:
        case=_case_for_context(original,context_available)
        start=time.perf_counter();before=0;error=None;route=None;usage={"calls":0,"input_tokens":None,"output_tokens":None}
        with app.db() as c:
            before=c.execute("SELECT COUNT(*) FROM paw_provider_calls WHERE task_id=?",(budget_id,)).fetchone()[0]
        try:
            route=__import__("supervisor").decide(case["request"],conversation,repo,app._heuristic_route,task_id=budget_id)
            actual=(route.get("supervisor_decision") or {}).get("intent")
            if actual not in VALID_INTENTS:raise ValueError("Supervisor returned an invalid benchmark intent")
        except (ValueError,OSError,TimeoutError) as exc:
            error=type(exc).__name__+": "+str(exc)
            route=route or {}
            actual=None
        elapsed=(time.perf_counter()-start)*1000
        with app.db() as c:
            entries=c.execute("SELECT input_tokens,output_tokens FROM paw_provider_calls WHERE task_id=? ORDER BY id",(budget_id,)).fetchall()
        usage={"calls":max(0,len(entries)-before),"input_tokens":sum(r[0] or 0 for r in entries[before:]) if entries[before:] else None,
               "output_tokens":sum(r[1] or 0 for r in entries[before:]) if entries[before:] else None}
        # Trust only the validated proposal attached by decide; fallback decisions retain an error.
        row=_row(case,actual,route,error,elapsed,usage)
        row["decision_source"]="ai-supervisor" if actual else "failed-no-fallback"
        rows.append(row)
    return rows,repo


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-ai",action="store_true",help="Invoke only an explicitly configured Qwen API Supervisor")
    parser.add_argument("--config",type=Path);parser.add_argument("--state",type=Path)
    parser.add_argument("--repo",help="Allowlisted repository for optional AI routing; defaults to the first configured repository")
    parser.add_argument("--conversation",help="Existing authorized conversation used for bounded context resolution; no conversation is created")
    parser.add_argument("--ai-call-budget",type=int);parser.add_argument("--ai-max-cases",type=int,default=6)
    args=parser.parse_args(argv)
    heuristic=_heuristic_rows()
    plans=_decision_plans(heuristic)
    report={"scope":"Routing decision replay only. It does not run workers, native CLIs, verifiers, or measure task completion quality.",
            "expected_labels":"Independent fixed English/Thai labels in this source; invalid model enum values remain errors.",
            "repository":args.repo or "routing-only; optional AI mode uses first configured repository",
            "heuristic":{"rows":heuristic,"score":score(heuristic)},"fixed_native_policy":plans["fixed_native"],"hybrid_policy":plans["hybrid"],
            "configured_ai_supervisor":None}
    if args.run_ai:
        if not args.config or not args.state or args.ai_call_budget is None:parser.error("--run-ai requires --config, --state, and --ai-call-budget")
        rows,selected_repo=_ai_rows(str(args.config),str(args.state),args.ai_call_budget,args.ai_max_cases,args.repo,args.conversation)
        report["repository"]=selected_repo
        report["configured_ai_supervisor"]={"rows":rows,"score":score(rows),"model":"empero-ai/Qwen3.8-9B-Distill"}
        report["hybrid_policy_from_configured_ai"]=_decision_plans(rows)["hybrid"]
    elif args.config or args.state or args.ai_call_budget is not None or args.conversation:
        parser.error("Configuration and budget flags require --run-ai")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0


if __name__=="__main__":raise SystemExit(main())
