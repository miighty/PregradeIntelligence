#!/usr/bin/env node
import 'source-map-support/register.js';
import * as cdk from 'aws-cdk-lib';
import { PregradeApiStack } from '../lib/pregrade-api-stack.js';

const app = new cdk.App();

new PregradeApiStack(app, 'PregradeApiStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
});
