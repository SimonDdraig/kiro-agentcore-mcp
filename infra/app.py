# Copyright 2025 Bush Ranger AI Project. All rights reserved.
"""CDK entry point for the Bush Ranger AI infrastructure stack."""

import aws_cdk as cdk
from stacks.bush_ranger_stack import BushRangerStack

app = cdk.App()

BushRangerStack(
    app,
    "BushRangerStack",
    env=cdk.Environment(
        account=app.node.try_get_context("account") or None,
        region="us-east-1",
    ),
)

app.synth()
