import subprocess
import sys

SA_ID = "aje4dvfc3964dgg1d74t"  # sa-apigw-exec
FUNCTION_IDS = [
    # employees-and-firms-api
    "d4e6qqejob02kq2j8l4l",  # get-user-data
    "d4ep4vks5f5ahnbb6i45",  # create-firm
    "d4e7poo87ijl346vpetg",  # delete-firm
    "d4eqvcfq7j6rgrc7ii3q",  # invite-employee
    "d4er1pebqu5om94082c3",  # employee-manager
    # tariffs-and-storage-api
    "d4eldr0g66rsnknt8cvf",  # tariffs-and-storage-manager
    "d4em90c6ufbfiss95ag4",  # edit-integrations
    # notifications-api
    "d4e6pc9kpgijmt3ii2v9",  # endpoints-manager
    "d4e3v8k2iijejj8du1t1",  # notices-manager
]
AUTHORIZER_ID = "d4eko30p260oae7m3rfa"


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def grant_invoker(fn_id: str) -> None:
    cmd = [
        "yc", "serverless", "function", "add-access-binding",
        "--id", fn_id,
        "--role", "serverless.functions.invoker",
        "--service-account-id", SA_ID,
    ]
    res = run(cmd)
    if res.returncode != 0:
        print(f"[WARN] add-access-binding failed for {fn_id}: rc={res.returncode}\n{res.stderr.strip()}")
    else:
        print(f"[OK] invoker granted for {fn_id}")


def list_bindings(fn_id: str) -> None:
    res = run(["yc", "serverless", "function", "list-access-bindings", "--id", fn_id])
    if res.returncode != 0:
        print(f"[ERR] list-access-bindings failed for {fn_id}: rc={res.returncode}\n{res.stderr.strip()}")
        return
    print(f"--- Access bindings for {fn_id} ---")
    print(res.stdout.strip())


def main() -> int:
    print(f"Grant invoker role to SA {SA_ID} on {len(FUNCTION_IDS)} functions and authorizer {AUTHORIZER_ID}\n")
    for fid in FUNCTION_IDS:
        grant_invoker(fid)
    grant_invoker(AUTHORIZER_ID)

    print("\nVerification:\n")
    for fid in FUNCTION_IDS + [AUTHORIZER_ID]:
        list_bindings(fid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
