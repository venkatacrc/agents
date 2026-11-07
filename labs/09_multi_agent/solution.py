"""Lab 09 reference: an orchestrator that delegates to sub-agents with their own context windows."""
from concurrent.futures import ThreadPoolExecutor

from agentlab.loop import run_agent

LEAD = ("You lead a research team. Split the task into independent research questions, one per line, "
        "each answerable on its own. Reply with the questions only.")
RESEARCHER = ("You research one question with search and read. Reply with a finding of at most three sentences "
              "that quotes the key numbers and caveats and names the documents you used.")
WRITER = "You write the final brief from your team's findings. Be concise and keep every number."


def subagent(llm, question, tools, max_steps=8):
    run = run_agent(llm, tools, question, system=RESEARCHER, max_steps=max_steps)
    return run.answer.strip()


def orchestrate(llm, task, tools, workers=4):
    plan = llm.chat([{"role": "system", "content": LEAD}, {"role": "user", "content": task}]).text
    questions = [q.strip(" -*0123456789.)") for q in plan.splitlines() if q.strip()]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        findings = list(pool.map(lambda q: subagent(llm, q, tools), questions))
    notes = "\n\n".join(f"Question: {q}\nFinding: {f}" for q, f in zip(questions, findings))
    brief = llm.chat([{"role": "system", "content": WRITER},
                      {"role": "user", "content": f"Task: {task}\n\n{notes}"}]).text
    return brief, questions, findings
