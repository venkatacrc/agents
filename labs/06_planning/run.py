"""Check Lab 06: plan a trip, hit a sold-out hotel, replan, and compare with one long ReAct run.

Usage: python labs/06_planning/run.py [--solution] [--trace] [--model ollama:NAME]
"""
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from agentlab import get_llm  # noqa: E402
from agentlab.kb import calculator  # noqa: E402
from agentlab.labs import header, lab_args, load_impl, record, report, todo_hint  # noqa: E402
from agentlab.loop import run_agent  # noqa: E402
from agentlab.mock import call, last_user, results_of, say, system_text  # noqa: E402
from agentlab.tools import tool  # noqa: E402
from agentlab.trace import Printer  # noqa: E402

args = lab_args(__doc__)
header(__file__, args.solution, args.model)
m = load_impl(__file__, args.solution)

FLIGHTS = [("TAP 236", 812), ("United 94", 958), ("Lufthansa 455", 870)]
HOTELS = [("Casa Azul", 145), ("Hotel Lusitano", 168), ("Palacio Real", 240), ("Alfama Rooms", 199)]
SOLD_OUT = {"Casa Azul"}
EUR_USD = 1.08


@tool
def search_flights(origin: str, destination: str, month: str) -> str:
    """Search round-trip economy flights; prices in USD.

    Args:
        origin: airport code, e.g. SFO
        destination: city or airport, e.g. Lisbon
        month: travel month, e.g. March
    """
    return "; ".join(f"{f}: {p} USD" for f, p in FLIGHTS)


@tool
def search_hotels(city: str, max_eur_per_night: float) -> str:
    """Search hotels in a city at or under a nightly price in EUR, cheapest first.

    Args:
        city: city name
        max_eur_per_night: the most to pay per night, in EUR
    """
    ok = sorted((p, h) for h, p in HOTELS if p <= float(max_eur_per_night))
    return "; ".join(f"{h}: {p} EUR/night" for p, h in ok) or "no hotels under that price"


@tool
def check_availability(hotel: str, nights: int) -> str:
    """Check whether a hotel has a room for the given number of nights in March.

    Args:
        hotel: hotel name from search_hotels
        nights: number of nights
    """
    return f"{hotel}: sold out" if hotel in SOLD_OUT else f"{hotel}: available for {nights} nights"


@tool
def convert(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert money between EUR and USD at today's rate.

    Args:
        amount: the amount to convert
        from_currency: EUR or USD
        to_currency: EUR or USD
    """
    rate = EUR_USD if from_currency.upper() == "EUR" else 1 / EUR_USD
    return f"{float(amount) * rate:.2f} {to_currency.upper()}"


TOOLS = [search_flights, search_hotels, check_availability, convert, calculator]
TASK = ("Plan a 3-night trip from SFO to Lisbon in March: the cheapest flight, the cheapest available hotel under "
        "200 EUR a night, and the total cost in USD.")


def hotel_after(text, skip):
    for name, price in re.findall(r"([A-Z][\w ]+?): (\d+) EUR/night", text):
        if name.strip() not in skip:
            return name.strip(), int(price)
    return None


def step_policy(step, messages, context):
    """The executor: the minimum tool use for one step, using results passed in the step's context."""
    s = step.lower()
    if "flight" in s:
        found = results_of(messages, "search_flights")
        if not found:
            return call("search_flights", origin="SFO", destination="Lisbon", month="March")
        best = min(re.findall(r"([\w ]+?): (\d+) USD", found[-1]), key=lambda x: int(x[1]))
        return say(f"Cheapest flight: {best[0].strip()} at {best[1]} USD")
    if "find hotels" in s or "search hotels" in s:
        found = results_of(messages, "search_hotels")
        if not found:
            return call("search_hotels", city="Lisbon", max_eur_per_night=200)
        return say("Hotels under 200 EUR: " + found[-1])
    if "availability" in s:
        named = re.search(r"hotel, ([A-Z][\w ]+?), for", step)
        target = named.group(1) if named else hotel_after(context, set())[0]
        found = results_of(messages, "check_availability")
        if not found:
            return call("check_availability", hotel=target, nights=3)
        if "sold out" in found[-1]:
            return say(f"FAILED: {target} is sold out for those nights")
        return say(f"{target} is available for 3 nights")
    if "total" in s:
        avail = re.findall(r"([A-Z][\w ]+?) is available", context)
        hotel = avail[-1]
        price = dict((n.strip(), int(p)) for n, p in re.findall(r"([A-Z][\w ]+?): (\d+) EUR/night", context))[hotel]
        flight = int(re.search(r"at (\d+) USD", context).group(1))
        conv = results_of(messages, "convert")
        if not conv:
            return call("convert", amount=3 * price, from_currency="EUR", to_currency="USD")
        sums = results_of(messages, "calculator")
        usd = conv[-1].split()[0]
        if not sums:
            return call("calculator", expression=f"{flight} + {usd}")
        return say(f"Total: {sums[-1]} USD (flight {flight} USD + 3 nights at {hotel}, {3 * price} EUR = {usd} USD)")
    return say(f"FAILED: don't know how to do '{step}'")


def policy(messages, tools):
    system, user = system_text(messages), last_user(messages)
    if system.startswith("You are a planner"):
        return say("1. Find the cheapest flight from SFO to Lisbon in March\n"
                   "2. Find hotels in Lisbon under 200 EUR per night\n"
                   "3. Check availability of the cheapest hotel for 3 nights\n"
                   "4. Compute the total cost in USD")
    if system.startswith("You revise plans"):
        failed = re.search(r"FAILED: ([A-Z][\w ]+?) is sold out", user).group(1)
        nxt = hotel_after(user, {failed})[0]
        return say(f"1. Check availability of the next cheapest hotel, {nxt}, for 3 nights\n"
                   "2. Compute the total cost in USD")
    if system.startswith("You execute one step"):
        first = next(x["content"] for x in messages if x["role"] == "user")
        step = re.match(r"Step: (.*)", first).group(1)
        return step_policy(step, messages, first + "\n" + "\n".join(results_of(messages, "check_availability")))
    return react_policy(messages)


def react_policy(messages):
    """The same work as one long ReAct run: one context holds every step."""
    flights = results_of(messages, "search_flights")
    if not flights:
        return call("search_flights", origin="SFO", destination="Lisbon", month="March")
    hotels = results_of(messages, "search_hotels")
    if not hotels:
        return call("search_hotels", city="Lisbon", max_eur_per_night=200)
    checks = results_of(messages, "check_availability")
    tried = {c.split(":")[0] for c in checks}
    if not checks or "sold out" in checks[-1]:
        return call("check_availability", hotel=hotel_after(hotels[-1], tried)[0], nights=3)
    hotel = checks[-1].split(":")[0]
    price = dict((n.strip(), int(p)) for n, p in re.findall(r"([A-Z][\w ]+?): (\d+) EUR/night", hotels[-1]))[hotel]
    flight = min(int(p) for p in re.findall(r"(\d+) USD", flights[-1]))
    conv = results_of(messages, "convert")
    if not conv:
        return call("convert", amount=3 * price, from_currency="EUR", to_currency="USD")
    sums = results_of(messages, "calculator")
    if not sums:
        return call("calculator", expression=f"{flight} + {conv[-1].split()[0]}")
    return say(f"Total: {sums[-1]} USD")


try:
    llm = get_llm(args.model, policy)
    print("plan-and-execute, todo list as it runs:")
    answer, todos, replans = m.plan_and_execute(llm, TASK, TOOLS, verbose=True)
    plan_calls, plan_peak = llm.calls, llm.peak_prompt_tokens
    print(f"\nanswer: {answer}\nreplans: {replans}, {llm.usage()}")
except NotImplementedError as e:
    todo_hint(e, __file__)

react = get_llm(args.model, policy)
r = run_agent(react, TOOLS, TASK, max_steps=12, on_event=Printer() if args.trace else None)
print(f"\none ReAct run for comparison: {r.answer}\n  {react.usage()}")
total = re.search(r"Total: ([\d.]+)", answer)
total = float(total.group(1)) if total else None
record(plan_steps=4, replans=replans, total_usd=total, plan_peak=plan_peak, react_peak=react.peak_prompt_tokens)
report(
    "planning first turns one long, growing context into short focused ones: each step's executor sees only its "
    "step and the results it needs, and a failure triggers a replan instead of derailing the whole run",
    f"total {total} USD after {replans} replan (Casa Azul was sold out); peak prompt {plan_peak} tokens with "
    f"planning vs {react.peak_prompt_tokens} for one ReAct context, at {plan_calls} vs {react.calls} model calls",
    "PASS" if total == 1356.32 and replans == 1 else "CHECK: expected 1356.32 USD after one replan",
    "make the replanner return the original plan unchanged and watch max_replans stop the loop; then add a "
    "'verify the plan' call before executing, as many production planners do",
)
