"""
בדיקות לשרשרת המודלים - בלי לשלוח אף בקשה אמיתית (מודלים מדומים).
הרצה:  python tests/test_llm_chain.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from lib import llm  # noqa: E402

OK = '{"status": "answered", "answer": "x", "sources": []}'


def fake(behavior, log):
    """behavior: "ok" / "429" / "day" / "503" / ("slow", שניות)"""
    def call(model, system, prompt, schema):
        log.append(model)
        if behavior == "ok":
            return OK
        if behavior == "429":
            raise llm.ModelError("429 Rate limit reached (per minute)")
        if behavior == "day":
            raise llm.ModelError("429 GenerateRequestsPerDayPerProjectPerModel")
        if behavior == "503":
            raise llm.ModelError("503 high demand")
        time.sleep(behavior[1])
        return OK
    return call


def setup(*behaviors):
    log = []
    llm.CHAIN[:] = [(f"m{i}", fake(b, log)) for i, b in enumerate(behaviors)]
    llm._blocked_until.clear()
    return log


def run(name, check):
    t = time.time()
    try:
        check()
        print(f"✓ {name}  ({time.time() - t:.1f}s)")
    except AssertionError as e:
        print(f"✗ {name}: {e}")
        sys.exit(1)


valid = lambda d: isinstance(d, dict)  # noqa: E731


def t_fallback():                     # 429 בראשון -> עוברים מיד לשני
    log = setup("429", "ok")
    t = time.time()
    _, model = llm.generate_json("", "", {}, valid)
    assert model == "m1" and time.time() - t < 1, (model, log)
    assert llm._blocked_until["m0"] - time.time() > 50, "m0 צריך להיחסם לדקה"


def t_day_block():                    # מכסה יומית -> חסום ל-3 שעות, לא נוסה שוב
    log = setup("day", "ok")
    llm.generate_json("", "", {}, valid)
    log.clear()
    llm.generate_json("", "", {}, valid)
    assert log == ["m1"], log


def t_hedge():                        # הראשון איטי -> אחרי 5 שניות רץ במקביל השני, הוא מנצח
    setup(("slow", 12), "ok")
    t = time.time()
    _, model = llm.generate_json("", "", {}, valid)
    took = time.time() - t
    assert model == "m1" and 4.5 < took < 6.5, (model, took)


def t_backoff():                      # כולם נכשלים -> 3 סבבים (0, 1, 3 שניות), ואז שגיאה מסודרת
    log = setup("503", "429")
    t = time.time()
    try:
        llm.generate_json("", "", {}, valid)
        raise AssertionError("ציפינו לשגיאה")
    except llm.ModelError:
        pass
    took = time.time() - t
    assert len(log) == 6 and 3.5 < took < 5.5, (log, took)


def t_chain_survives():               # הבאג שנמצא: כשכולם חסומים, הרשימה CHAIN התרוקנה לתמיד
    setup("503", "503")
    for _ in range(4):
        try:
            llm.generate_json("", "", {}, valid)
        except llm.ModelError:
            pass
    assert len(llm.CHAIN) == 2, f"CHAIN התקצר ל-{len(llm.CHAIN)}"


def t_budget():                       # כולם תקועים -> עוצרים אחרי TOTAL_BUDGET, לא נתקעים
    setup(("slow", 30), ("slow", 30))
    llm.TOTAL_BUDGET = 8
    t = time.time()
    try:
        llm.generate_json("", "", {}, valid)
        raise AssertionError("ציפינו לשגיאה")
    except llm.ModelError:
        pass
    llm.TOTAL_BUDGET = 40
    assert time.time() - t < 9, time.time() - t


if __name__ == "__main__":
    real = list(llm.CHAIN)
    for name, f in [("429 -> מעבר מיידי למודל הבא", t_fallback),
                    ("מכסה יומית -> המודל מדולג בשאלות הבאות", t_day_block),
                    ("מודל איטי -> מירוץ מקביל אחרי 5 שניות", t_hedge),
                    ("כולם נכשלו -> Backoff של 1 ו-3 שניות", t_backoff),
                    ("רשימת המודלים לא מתרוקנת (באג שתוקן)", t_chain_survives),
                    ("תקרת זמן כוללת", t_budget)]:
        run(name, f)
    llm.CHAIN[:] = real
    print("כל הבדיקות עברו")
