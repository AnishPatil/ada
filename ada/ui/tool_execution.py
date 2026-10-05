"""Sequential execution of model tool batches with explicit dependency results.

Dependencies cover ADA's geometry, analysis-case, and analysis-data resources.
Unspecified indices follow the preceding resource-producing call; a single
later creator can supply a missing prerequisite. Ambiguous references fail
explicitly so the model can retry with concrete indices.
"""

import json
import time


XFOIL = "analysis_apis_xfoil_"
GEOMETRY_WRITERS = {"generateAirfoil", "copyGeometry", "modifyGeometry",
                    "increaseCamber", "changeActiveGeometry"}
CASE_WRITERS = {XFOIL + "addAnalysisCase", XFOIL + "modifyAnalysisCase",
                "copyAnalysis", "changeActiveAnalysis"}
DATA_READERS = {XFOIL + name for name in (
    "standardPlot", "boundaryLayerPlot", "forcePlot", "polarPlot", "sweepPlot"
)} | {"selectData", "deselectData"}
CREATORS = {"geometry": {"generateAirfoil", "copyGeometry"},
            "analysis": {XFOIL + "addAnalysisCase", "copyAnalysis"},
            "data": {"run"}}


def field(value, name, default=None):
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def is_default(value):
    return value is None or (isinstance(value, str) and value.strip().lower() in {"", "none", "null"})


def state_outputs(ui):
    active = ui.activeAnalysis
    return {
        "geometryIndex": ui.activeGeometry + 1 if ui.activeGeometry is not None else None,
        "toolName": active[0] if active is not None else None,
        "caseIndex": active[1] + 1 if active is not None else None,
        "dataIndicies": [index + 1 for index in (ui.activeDataItems or [])],
    }


def positive_index(value, count, label):
    text = str(value).strip()
    if not text.isdigit() or int(text) < 1 or int(text) > count:
        raise ValueError(f"{label} must identify an existing item (1..{count}); received {value!r}")
    return int(text)


def writes(name, resource):
    return name in {"geometry": GEOMETRY_WRITERS, "analysis": CASE_WRITERS,
                    "data": {"run", "selectData", "deselectData", "clearDataSelection"}}[resource]


def requirements(name, args, ui, names):
    needed = []
    if name in GEOMETRY_WRITERS - {"generateAirfoil"} or name == "run":
        needed.append("geometry")
    if name in CASE_WRITERS - {XFOIL + "addAnalysisCase"} or name == "run":
        needed.append("analysis")
    if name == XFOIL + "addAnalysisCase" and (
        not is_default(args.get("geometryIndex")) or ui.activeGeometry is not None
        or any(n in CREATORS["geometry"] for n in names)
    ):
        needed.append("geometry")
    if name in DATA_READERS:
        needed.append("data")
    return needed


def resolve_resource(resource, name, args, defaults, ui):
    """Resolve at execution time, after prerequisite calls have produced IDs."""
    if resource == "geometry":
        key = "activeGeometryIndex" if name == "changeActiveGeometry" else "geometryIndex"
        value = args.get(key)
        if is_default(value) or (name == "run" and value in (0, "0")):
            value = defaults["geometryIndex"]
        return {key: str(positive_index(value, len(ui.geometryItems), key))}
    if resource == "analysis":
        tool_key = "activeAnalysisTool" if name == "changeActiveAnalysis" else "toolName"
        case_key = "activeAnalysisIndex" if name == "changeActiveAnalysis" else "caseIndex"
        tool = args.get(tool_key)
        if is_default(tool):
            tool = "xfoil" if name.startswith(XFOIL) else defaults["toolName"]
        value = args.get(case_key)
        if is_default(value) or (name == "run" and value in (0, "0")):
            if tool != defaults["toolName"]:
                raise ValueError(f"No active case for tool {tool!r}; supply an explicit {case_key}")
            value = defaults["caseIndex"]
        count = len(ui.analysisItems.get(tool, []))
        return {tool_key: tool, case_key: str(positive_index(value, count, case_key))}
    value = args.get("dataIndicies")
    if is_default(value):
        value = defaults["dataIndicies"]
    elif isinstance(value, str):
        value = value.strip().strip("[](){}").split(",")
    if not isinstance(value, list) or not value:
        raise ValueError("No analysis data selected; run an analysis first or specify dataIndicies")
    indices = [positive_index(v, len(ui.dataItems), "dataIndicies") for v in value]
    return {"dataIndicies": json.dumps(indices)}


def implicit_reference(resource, name, args):
    key = {"geometry": "geometryIndex", "analysis": "caseIndex", "data": "dataIndicies"}[resource]
    if name == "changeActiveGeometry":
        key = "activeGeometryIndex"
    if name == "changeActiveAnalysis":
        key = "activeAnalysisIndex"
    return is_default(args.get(key)) or (name == "run" and args.get(key) in (0, "0"))


def execute_batch(ui, items, handles, prompt, port, cache, round_number, remaining):
    """Return a record for EVERY requested call, including failed/skipped calls.

    A prerequisite's captured outputs are used instead of whichever unrelated
    object happens to be active after reordering. Explicit indices are retained.
    """
    initial = state_outputs(ui)
    records = []
    for index, item in enumerate(items):
        record = {"call_id": field(item, "call_id") or field(item, "id")
                  or f"round_{round_number}_call_{index + 1}",
                  "name": field(item, "name"), "raw_arguments": field(item, "arguments", "{}"),
                  "status": "pending", "dependencies": {}, "execution_order": None}
        try:
            raw = record["raw_arguments"]
            args = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(args, dict):
                raise ValueError("Tool arguments must be a JSON object")
            record["arguments"] = dict(args)
        except (ValueError, TypeError) as exc:
            record.update(status="failed", result=f"ERROR: Invalid tool arguments: {exc}", outputs={})
        records.append(record)

    names = [r["name"] for r in records]
    for index, record in enumerate(records):
        if record["status"] != "pending":
            continue
        args = record["arguments"]
        record["requirements"] = requirements(record["name"], args, ui, names)
        for resource in record["requirements"]:
            try:
                target = resolve_resource(resource, record["name"], args, initial, ui)
                available = True
            except ValueError:
                available = False
            previous = [i for i in range(index) if writes(names[i], resource)]
            if available and not implicit_reference(resource, record["name"], args):
                # Existing explicit targets do not depend on unrelated new items.
                matching = []
                for i in previous:
                    if names[i] in CREATORS[resource] or resource == "data":
                        continue
                    try:
                        other = resolve_resource(resource, names[i], records[i].get("arguments", {}), initial, ui)
                        if list(other.values()) == list(target.values()):
                            matching.append(i)
                    except ValueError:
                        pass
                previous = matching
            if previous:
                record["dependencies"][resource] = previous[-1]
                continue
            if implicit_reference(resource, record["name"], args) or not available:
                future = [i for i in range(index + 1, len(records)) if names[i] in CREATORS[resource]]
                if len(future) == 1:
                    record["dependencies"][resource] = future[0]
                elif len(future) > 1:
                    record.update(status="failed", outputs={}, result=(
                        f"ERROR: Ambiguous {resource} dependency; multiple later creators. "
                        "Create the items first, then retry with explicit indices."
                    ))

    execution_count = 0
    visiting = set()

    def execute(index):
        nonlocal execution_count
        record = records[index]
        if record["status"] != "pending":
            return
        if index in visiting:
            record.update(status="skipped", result="ERROR: Cyclic tool dependencies; reorder the calls.", outputs={})
            return
        visiting.add(index)
        try:
            for dependency in record["dependencies"].values():
                execute(dependency)
                if records[dependency]["status"] not in {"succeeded", "reused"}:
                    record.update(status="skipped", outputs={}, result=(
                        f"ERROR: Prerequisite {records[dependency]['call_id']} did not succeed."
                    ))
                    return
            old = cache.get(record["call_id"])
            if old is not None:
                if old["name"] != record["name"] or old["arguments"] != record["arguments"]:
                    raise ValueError("A previously used call ID was reused with different arguments")
                record.update(status="reused" if old["status"] == "succeeded" else old["status"],
                              result=old["result"], outputs=old["outputs"])
                return
            if execution_count >= remaining:
                record.update(status="skipped", result="ERROR: Tool-call execution limit reached.", outputs={})
                return
            if record["name"] not in handles:
                raise ValueError(f"Unknown tool {record['name']!r}")

            args = dict(record["arguments"])
            for resource in record["requirements"]:
                dependency = record["dependencies"].get(resource)
                defaults = records[dependency]["outputs"] if dependency is not None else initial
                args.update(resolve_resource(resource, record["name"], args, defaults, ui))
            record["effective_arguments"] = dict(args)
            # Some legacy tools use the active selection internally even with an
            # explicit index. Keep that selection consistent with resolved inputs.
            if "geometry" in record["requirements"]:
                geometry = args.get("activeGeometryIndex", args.get("geometryIndex"))
                ui.activeGeometry = int(geometry) - 1
            if "analysis" in record["requirements"]:
                tool = args.get("activeAnalysisTool", args.get("toolName"))
                case = args.get("activeAnalysisIndex", args.get("caseIndex"))
                ui.activeAnalysis = (tool, int(case) - 1)
            print(f"function name: {record['name']}")
            print(f"arguments(effective): {json.dumps(args)}")
            before_data = len(ui.dataItems)
            args.update(uiManager=ui, portNumber=port, rawInput=prompt)
            execution_count += 1
            record["execution_order"] = execution_count
            result = handles[record["name"]](**args)
            failed = isinstance(result, str) and result.lstrip().upper().startswith(("ERROR", "FAILURE"))
            outputs = state_outputs(ui)
            if record["name"] == "run":
                outputs["dataIndicies"] = list(range(before_data + 1, len(ui.dataItems) + 1))
                if not failed and not outputs["dataIndicies"]:
                    result = "ERROR: Analysis returned without producing any data."
                    failed = True
            record.update(status="failed" if failed else "succeeded", result=result, outputs=outputs)
        except Exception as exc:
            record.update(status="failed", result=f"ERROR executing {record['name']}: {exc!r}", outputs={})
        finally:
            visiting.discard(index)
            if record["status"] != "pending" and "arguments" in record:
                cache.setdefault(record["call_id"], dict(record))

    for index in range(len(records)):
        execute(index)
    return records, execution_count


def run_tool_loop(ui, call, prompt, function_data, handles, send, port, model,
                  max_rounds=20, max_tool_calls=100):
    """Execute batches, then feed their results and resource IDs back to the model."""
    cache = {}
    summaries = []
    execution_count = 0
    model_wait = 0.0
    call.tool_results = []
    call.model_responses = []
    guidance = (
        "\nExecute the requested workflow using tools. List prerequisite calls before their dependents. "
        "For dependent geometry/case/data indices, use 'None' to use the preceding tool's output. "
        "For multiple new items, create them first and then use their returned explicit indices. "
        "Use explicit 1-based indices when targeting an existing item. If an argument depends on a "
        "result you do not know yet, wait for that result before requesting the dependent call."
    )
    augmented_prompt = prompt + guidance
    try:
        for round_number in range(1, max_rounds + 1):
            started = time.perf_counter()
            response = send(augmented_prompt, function_data)
            model_wait += time.perf_counter() - started
            model = field(response, "model") or model
            output = field(response, "output", []) or []
            text = field(response, "output_text") or ""
            if not text:
                text = "\n".join(
                    field(part, "text") or field(part, "refusal") or ""
                    for item in output if field(item, "type") == "message"
                    for part in (field(item, "content", []) or [])
                ).strip()
            items = [item for item in output if field(item, "type") == "function_call"]
            call.model_responses.append({"round": round_number, "model": model,
                "status": field(response, "status"), "text": text,
                "error": field(response, "error"),
                "incomplete_details": field(response, "incomplete_details"),
                "output_types": [field(item, "type") for item in output]})
            if not items:
                if text:
                    plots = [r["result"] for r in call.tool_results
                             if r["status"] == "succeeded" and isinstance(r["result"], str)
                             and "<img" in r["result"]]
                    call.response = "<br>\n".join(plots + [text])
                elif call.response is None:
                    call.response = ("Tool calls completed without a final text response." if call.tool_results
                                     else "No function call or text response returned.")
                if field(response, "status") in {"failed", "incomplete", "cancelled"}:
                    call.response = f"ERROR: Model response status: {field(response, 'status')}. {text}"
                break

            print("==================================================")
            print(f"Model response round: {round_number}; requested functions: {len(items)}")
            call.tool_calls.extend(field(item, "name") or "(unnamed)" for item in items)
            records, executed = execute_batch(ui, items, handles, prompt, port, cache,
                                              round_number, max_tool_calls - execution_count)
            execution_count += executed
            call.tool_results.extend(records)
            for record in records:
                result = str(record.get("result"))
                summaries.append(json.dumps({"call_id": record["call_id"], "name": record["name"],
                    "status": record["status"], "arguments": record.get("effective_arguments", record.get("arguments")),
                    "result": result[:1000], "outputs": record.get("outputs")}, default=str))
            completed = sorted((r for r in records if r["execution_order"] is not None),
                               key=lambda r: r["execution_order"])
            if completed:
                call.interpretation = " -> ".join(r["name"] for r in completed)
                call.response = completed[-1]["result"]
            augmented_prompt = (prompt + guidance + "\n\nTool outcomes (do not repeat successful calls):\n"
                + "\n".join(summaries)
                + "\nFor geometry edits, track completed K indices and use index-specific values unless "
                  "the user requested uniform values. Request any remaining actions, or respond with text "
                  "and no tool calls when the request is complete. Report failures honestly.")
            if execution_count >= max_tool_calls:
                call.response = f"ERROR: Stopped after {max_tool_calls} tool executions."
                break
        else:
            call.response = f"ERROR: Stopped after {max_rounds} model response rounds."
    except Exception as exc:
        # Preserve completed calls in the session log if a later model request fails.
        call.response = f"ERROR in model response loop: {exc!r}"
    finally:
        failures = [r for r in call.tool_results if r["status"] in {"failed", "skipped"}]
        if failures:
            call.response = (str(call.response or "") + "\nERROR: Some requested tools did not complete:\n"
                             + "\n".join(f"{r['name']}: {r['result']}" for r in failures))
        print(f"[LLM timing] Total response time: {model_wait:.2f} seconds")
        print(f"[LLM runtime] Model used: {model}")
