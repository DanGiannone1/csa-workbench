# Publishing Note: AI Agent Evals Team Guide

I am sharing the **AI Agent Evals Team Guide** as a practical reference for teams building, reviewing, or operating AI agent systems.

The guide explains how to evaluate agents beyond a single successful demo. It covers how to define eval tasks, record complete transcripts, separate deterministic code graders from LLM judges, measure reliability with repeated trials, evaluate skills, and use Waza-style skill-laboratory checks alongside full product-runtime evals.

This document is intended for a wider audience of AI agent builders, product owners, engineering leads, evaluators, and stakeholders who need a shared vocabulary for agent quality, safety, reliability, and readiness.

Key topics include:

- What AI agent evals are and why they differ from traditional software tests
- How to design realistic eval tasks and repeatable eval suites
- When to use deterministic graders, LLM judges, and human review
- How to interpret `pass@k` and `pass^k` reliability metrics
- How to evaluate agent skills, including Waza-style skill-laboratory evals
- What provenance and config stamps are needed for trustworthy scorecards
- Common eval anti-patterns and governance considerations before publication or release

The recommended document for broad sharing is:

`eval/AI_Agent_Evals_Team_Guide_General_v2.docx`

Suggested positioning:

> This guide is a practical starting point for teams that want to make AI agent behavior measurable, repeatable, and reviewable. It is not tied to one product implementation and can be adapted across agent frameworks, runtimes, and evaluation platforms.

Suggested request to reviewers:

> Please review for clarity, technical accuracy, missing evaluation scenarios, and whether the guidance is understandable for both technical and non-technical stakeholders involved in AI agent delivery.
