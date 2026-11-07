"""Lab 05 reference: three workflow patterns, where your code (not the model) owns the control flow."""
from concurrent.futures import ThreadPoolExecutor


def ask(llm, system, user):
    return llm.chat([{"role": "system", "content": system}, {"role": "user", "content": user}]).text.strip()


def route(llm, ticket, routes):
    labels = ", ".join(routes)
    label = ask(llm, f"Classify the support ticket. Reply with exactly one of: {labels}.", ticket).lower()
    label = next((r for r in routes if r in label), "other")
    if label == "other":
        return label, "Escalated to a human: no route matched."
    return label, ask(llm, routes[label], ticket)


def fan_out(llm, system, items, workers=8):
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda item: ask(llm, system, item), items))


def evaluate_optimize(llm, task, rubric, max_rounds=5):
    draft = ask(llm, "You write release notes.", task)
    history = []
    for rnd in range(1, max_rounds + 1):
        verdict = ask(llm, f"You review drafts against this rubric:\n{rubric}\n"
                           "Reply PASS, or FAIL: followed by what is missing.", draft)
        history.append((draft, verdict))
        if verdict.startswith("PASS"):
            return draft, rnd, history
        draft = ask(llm, "You write release notes.",
                    f"{task}\n\nYour previous draft:\n{draft}\n\nReviewer feedback:\n{verdict}\n\nRewrite the draft.")
    return draft, max_rounds, history
