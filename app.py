from flask import Flask, render_template, request
from graphviz import Digraph
from pyformlang.regular_expression import Regex
import traceback

app = Flask(__name__)

# --- 1. REGEX TO DFA COMPONENT ---
def sanitize_regex(regex_string):
    sanitized = regex_string.replace('+', '|')
    return sanitized

def regex_to_dfa_components(regex_string):
    sanitized_regex = sanitize_regex(regex_string)
    regex = Regex(sanitized_regex)
    dfa = regex.to_epsilon_nfa().to_deterministic()

    state_mapping = {}
    
    if dfa.start_state:
        state_mapping[dfa.start_state] = "q0"
        
    counter = 1 if dfa.start_state else 0
    for s in dfa.states:
        if s not in state_mapping:
            state_mapping[s] = f"q{counter}"
            counter += 1

    states = [state_mapping[s] for s in dfa.states]
    symbols = [str(sym.value) for sym in dfa.symbols]
    start = state_mapping[dfa.start_state] if dfa.start_state else (states[0] if states else "")
    final_states = [state_mapping[f] for f in dfa.final_states]

    transitions = {}
    for source_state, paths in dfa.to_dict().items():
        src = state_mapping[source_state]
        for symbol, target_state in paths.items():
            transitions[(src, str(symbol.value))] = state_mapping[target_state]
            
    return states, symbols, start, final_states, transitions


# --- 2. DFA MINIMIZATION LOGIC WITH EXPLANATIONS ---
def minimize_dfa(states, symbols, start, final_states, transitions):
    states, symbols, final_states = set(states), set(symbols), set(final_states)

    reachable = {start}
    while True:
        new = set()
        for s in reachable:
            for sym in symbols:
                target = transitions.get((s, sym))
                if target: new.add(target)
        if new <= reachable: break
        reachable |= new

    final_states &= reachable
    non_final = reachable - final_states

    P = []
    if non_final: P.append(non_final)
    if final_states: P.append(final_states)

    iterations = []
    
    iterations.append({
        "groups": [sorted(list(g)) for g in P],
        "reason": "0-Equivalence: Separated states into Non-Final and Final groups based on acceptance."
    })

    def get_signature(state, current_partition):
        sig = []
        for sym in sorted(list(symbols)):
            nxt = transitions.get((state, sym))
            for i, group in enumerate(current_partition):
                if nxt in group:
                    sig.append(i)
                    break
        return tuple(sig)

    step_num = 1
    while True:
        new_P = []
        split_details = []

        for group in P:
            signatures = {}
            for s in group:
                sig = get_signature(s, P)
                signatures.setdefault(sig, set()).add(s)
            
            if len(signatures) > 1:
                group_str = "{" + ", ".join(sorted(list(group))) + "}"
                split_details.append(f"Group {group_str} was split because its states transition to different destination groups.")

            new_P.extend(signatures.values())

        if len(new_P) == len(P):
            iterations.append({
                "groups": [sorted(list(g)) for g in new_P],
                "reason": "Partitions stabilized. No further splits can be made because all grouped states behave identically."
            })
            break

        iterations.append({
            "groups": [sorted(list(g)) for g in new_P],
            "reason": f"{step_num}-Equivalence: " + " ".join(split_details)
        })
        
        P = new_P
        step_num += 1

    state_map = {}
    for group in P:
        name = "".join(sorted(list(group)))
        for s in group: state_map[s] = name

    new_states = set(state_map.values())
    new_start = state_map[start]
    new_final = {state_map[s] for s in final_states}

    new_trans = {}
    for group in P:
        rep = next(iter(group))
        for sym in symbols:
            target = transitions.get((rep, sym))
            if target:
                new_trans[(state_map[rep], sym)] = state_map[target]

    return iterations, new_states, new_start, new_final, new_trans


# --- 3. GRAPH GENERATION (SVG OUTPUT) ---
def generate_graph_svg(states, transitions, final_states, start):
    dot = Digraph()
    dot.attr(rankdir='LR') # Removed size constraints to stop small graphs from stretching
    dot.attr('node', fontname='Poppins', fontsize='12')

    for s in states:
        if s in final_states: dot.node(s, shape="doublecircle")
        else: dot.node(s, shape="circle")

    for (s, sym), nxt in transitions.items():
        dot.edge(s, nxt, label=sym)

    dot.node("start", shape="point", width="0")
    dot.edge("start", start)

    return dot.pipe(format='svg').decode('utf-8')


# --- 4. ROUTES ---
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            regex_input = request.form.get("regex_input")
            
            if regex_input:
                states, symbols, start, finals, transitions = regex_to_dfa_components(regex_input)
            else:
                states = request.form.get("states", "").split()
                symbols = request.form.get("symbols", "").split()
                start = request.form.get("start", "")
                finals = request.form.get("final", "").split()

                if start not in states:
                    return render_template("index.html", error="Invalid start state")

                transitions = {}
                for s in states:
                    for sym in symbols:
                        val = request.form.get(f"{s}_{sym}")
                        if val:
                            transitions[(s, sym)] = val

            original_svg_graph = generate_graph_svg(states, transitions, finals, start)

            iterations, new_states, new_start, new_final, new_trans = minimize_dfa(
                states, symbols, start, finals, transitions
            )

            minimized_svg_graph = generate_graph_svg(new_states, new_trans, new_final, new_start)

            return render_template(
                "result.html",
                states=new_states,
                start=new_start,
                final=new_final,
                transitions=new_trans,
                iterations=iterations,
                symbols=symbols,
                original_graph=original_svg_graph,
                graph=minimized_svg_graph
            )
        except Exception as e:
            traceback.print_exc()
            error_msg = f"Error processing Regex: Invalid syntax. Ensure valid operators." if regex_input else f"Error: {str(e)}"
            return render_template("index.html", error=error_msg)

    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)