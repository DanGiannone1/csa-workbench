"""Cross-platform fake git/Azure CLI used by deployment contract tests."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

command = os.environ["FAKE_COMMAND"]
args = sys.argv[1:]
joined = " ".join(args)

if command == "git":
    if args[:1] == ["rev-parse"]:
        print("0123456789abcdef0123456789abcdef01234567")
    elif args[:1] != ["status"]:
        raise SystemExit(1)
    raise SystemExit(0)

log = os.environ.get("AZ_LOG")
if log:
    with Path(log).open("a", encoding="utf-8") as stream:
        stream.write(f"{joined}\n")

recovery = os.environ.get("FAKE_RECOVERY") == "1"
apps_mode = os.environ.get("FAKE_RECOVERY_APPS", "expected")
profile = os.environ.get("FAKE_RECOVERY_PROFILE", "incompatible")
bad_recovery = os.environ.get("FAKE_BAD_RECOVERY") == "1"
base = "csa-wb-mvp1"
environment_id = "env-id"
apps = {
    "expected": [f"{base}-frontend", f"{base}-api", f"{base}-runtime"],
    "reordered": [f"{base}-runtime", f"{base}-frontend", f"{base}-api"],
    "missing": [],
    "extra": [f"{base}-frontend", f"{base}-api", f"{base}-runtime", "unrelated"],
}[apps_mode]
app_inventory: object = [
    {"name": name, "properties": {"managedEnvironmentId": environment_id}}
    for name in apps
]
if bad_recovery:
    app_inventory = [{"name": 42}]
expected_subnet = (
    "/subscriptions/subscription/resourceGroups/csa-wb-mvp1-rg/providers/"
    "Microsoft.Network/virtualNetworks/csa-wb-mvp1-vnet/subnets/aca-infrastructure"
)
properties = {
    "incompatible": {"provisioningState": "Failed", "staticIp": None, "vnetConfiguration": {}, "workloadProfiles": []},
    "azure-enriched": {"provisioningState": "Succeeded", "staticIp": "20.42.33.145", "vnetConfiguration": {"infrastructureSubnetId": expected_subnet}, "workloadProfiles": [{"enableFips": False, "name": "Consumption", "workloadProfileType": "Consumption"}]},
    "azure-shell": {"provisioningState": "Succeeded", "staticIp": None, "vnetConfiguration": {"infrastructureSubnetId": expected_subnet}, "workloadProfiles": [{"enableFips": False, "name": "Consumption", "workloadProfileType": "Consumption"}]},
}[profile]

if joined == "account show --only-show-errors":
    print("{}")
elif joined == "account show --query tenantId -o tsv":
    print("tenant")
elif joined == "account show --query id -o tsv":
    print("subscription")
elif joined == "bicep version" or joined.startswith("bicep build "):
    pass
elif joined == f"group exists -n {base}-rg -o tsv":
    print("true" if recovery else "false")
elif joined.startswith("network nsg list "):
    print("[]")
elif joined.startswith("containerapp env list "):
    print(json.dumps([{"name": f"{base}-env", "id": environment_id}] if recovery else []))
elif joined.startswith("containerapp env show "):
    print(json.dumps({"name": f"{base}-env", "properties": properties}))
elif joined.startswith("containerapp list "):
    print(json.dumps(app_inventory))
elif joined.startswith("deployment sub create "):
    raise SystemExit(9)
