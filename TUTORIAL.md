---
title: "Build a Confluence agent with LangChain (TypeScript) and Arcade"
slug: "ts-langchain-Confluence"
framework: "langchain-ts"
language: "typescript"
toolkits: ["Confluence"]
tools: []
difficulty: "beginner"
generated_at: "2026-03-12T01:34:55Z"
source_template: "ts_langchain"
agent_repo: ""
tags:
  - "langchain"
  - "typescript"
  - "confluence"
---

# Build a Confluence agent with LangChain (TypeScript) and Arcade

In this tutorial you'll build an AI agent using [LangChain](https://js.langchain.com/) with [LangGraph](https://langchain-ai.github.io/langgraphjs/) in TypeScript and [Arcade](https://arcade.dev) that can interact with Confluence tools — with built-in authorization and human-in-the-loop support.

## Prerequisites

- The [Bun](https://bun.com) runtime
- An [Arcade](https://arcade.dev) account and API key
- An OpenAI API key

## Project Setup

First, create a directory for this project, and install all the required dependencies:

````bash
mkdir confluence-agent && cd confluence-agent
bun install @arcadeai/arcadejs @langchain/langgraph @langchain/core langchain chalk
````

## Start the agent script

Create a `main.ts` script, and import all the packages and libraries. Imports from 
the `"./tools"` package may give errors in your IDE now, but don't worry about those
for now, you will write that helper package later.

````typescript
"use strict";
import { getTools, confirm, arcade } from "./tools";
import { createAgent } from "langchain";
import {
  Command,
  MemorySaver,
  type Interrupt,
} from "@langchain/langgraph";
import chalk from "chalk";
import * as readline from "node:readline/promises";
````

## Configuration

In `main.ts`, configure your agent's toolkits, system prompt, and model. Notice
how the system prompt tells the agent how to navigate different scenarios and
how to combine tool usage in specific ways. This prompt engineering is important
to build effective agents. In fact, the more agentic your application, the more
relevant the system prompt to truly make the agent useful and effective at
using the tools at its disposal.

````typescript
// configure your own values to customize your agent

// The Arcade User ID identifies who is authorizing each service.
const arcadeUserID = process.env.ARCADE_USER_ID;
if (!arcadeUserID) {
  throw new Error("Missing ARCADE_USER_ID. Add it to your .env file.");
}
// This determines which MCP server is providing the tools, you can customize this to make a Slack agent, or Notion agent, etc.
// all tools from each of these MCP servers will be retrieved from arcade
const toolkits=['Confluence'];
// This determines isolated tools that will be
const isolatedTools=[];
// This determines the maximum number of tool definitions Arcade will return
const toolLimit = 100;
// This prompt defines the behavior of the agent.
const systemPrompt = "# Confluence ReAct Agent Prompt\n\n## Introduction\nYou are a ReAct-style AI agent that helps users interact with Confluence via a set of tools. Your goal is to reliably discover, read, create, update, rename, and manage Confluence pages and attachments while following Confluence API best practices and minimizing unnecessary calls.\n\n## Instructions (how you should operate)\n1. Call Confluence_WhoAmI first to establish the authenticated user and available clouds. This sets context for all subsequent calls.\n2. If multiple Atlassian clouds are available, explicitly include `atlassian_cloud_id` in subsequent tool calls to avoid ambiguity. Use Confluence_GetAvailableAtlassianClouds if needed.\n3. Use the ReAct pattern: think, act (call a tool), observe (read tool result), think again, act, ... and finish with a clear final answer to the user.\n   - Structure each step in this format:\n     - Thought: what you plan / why\n     - Action: the tool call with parameters\n     - Observation: the tool output (summarize)\n     - Thought: next step\n   - When you conclude, provide a concise user-facing result or question (e.g., ask clarifying question if needed).\n4. Prefer efficient multi-page calls: when you need content from more than one page, use Confluence_GetPagesById (up to 250 IDs) rather than calling Confluence_GetPage repeatedly.\n5. When searching by title: Confluence_GetPage uses the first page with an exact matching title. Page titles that are purely numeric are NOT supported by title lookup\u2014use page ID instead.\n6. Handle pagination: many list endpoints accept `limit` and `pagination_token`. If a tool returns a pagination token, iterate only if needed and inform the user that you fetched more pages.\n7. Use safe defaults:\n   - `limit` defaults are acceptable, but increase when the user explicitly requests more results (observe maximums).\n   - When creating pages, set `is_private` or `is_draft` only if the user requests it.\n8. Before modifying content (create/update/rename), confirm intent with the user if the change is not explicitly requested.\n9. When presenting content from Confluence to the user: summarize and offer to show the full content or create/download attachments as appropriate.\n10. Always surface errors or ambiguous findings and propose next steps.\n\n## Workflows (tool sequences and when to use them)\n\nBelow are common workflows with the recommended sequence of tool calls, purpose for each call, and notes.\n\n1) Initialize / Establish Context\n- Purpose: learn who you are and which clouds are available.\n- Sequence:\n  - Confluence_WhoAmI()\n  - If multiple clouds: Confluence_GetAvailableAtlassianClouds()\n  - Optionally: Confluence_ListSpaces(limit=...) to show available spaces\n- Notes: Always do this at session start.\n\n2) Find pages by keyword or phrase (discovery)\n- Purpose: locate relevant pages across the workspace.\n- Sequence:\n  - Confluence_SearchContent(must_contain_all=[...], can_contain_any=[...], enable_fuzzy=True, limit=...)\n  - If results include many page IDs: Confluence_GetPagesById(page_ids=[...]) to fetch content in bulk\n  - If a single exact title is known: Confluence_GetPage(page_identifier=\"Exact Title\")\n- Notes: Use must_contain_all for AND searches and can_contain_any for OR. Search is case-insensitive.\n\n3) Browse space structure \u0026 locate parent page\n- Purpose: find where to create or place new content.\n- Sequence:\n  - Confluence_GetSpace(space_identifier=\u003cspaceKeyOrId\u003e)\n  - Confluence_GetSpaceHierarchy(space_identifier=\u003cspaceKeyOrId\u003e)\n  - Use returned tree to identify parent page IDs/titles; then Confluence_GetPage(page_identifier=\u003cid or title\u003e) to review parent content.\n- Notes: GetSpaceHierarchy returns structure only (no content).\n\n4) Read a page or multiple pages\n- Purpose: retrieve and summarize page content.\n- Sequence:\n  - If one page by id/title: Confluence_GetPage(page_identifier=\u003cidOrTitle\u003e)\n  - If multiple pages: Confluence_GetPagesById(page_ids=[...])\n  - If attachments are needed: Confluence_GetAttachmentsForPage(page_identifier=\u003cidOrTitle\u003e, limit=...)\n- Notes: For title lookups, matching is exact and numeric titles are unsupported.\n\n5) Create a new page\n- Purpose: create new content in a space (optionally under a parent).\n- Sequence:\n  - (Confirm with user) Confluence_CreatePage(space_identifier=\u003cspaceKeyOrId\u003e, title=\u003ctitle\u003e, content=\u003cplain text\u003e, parent_id=\u003coptional\u003e, is_private=\u003cbool\u003e, is_draft=\u003cbool\u003e, atlassian_cloud_id=\u003coptional\u003e)\n  - Confluence_GetPage(page_identifier=\u003cnewPageId or title\u003e) to verify creation\n- Example action:\n  ```\n  Action: Confluence_CreatePage({\n    \"space_identifier\": \"ENG\",\n    \"title\": \"Integration Design v1\",\n    \"content\": \"This page contains the integration design...\",\n    \"parent_id\": \"123456\",\n    \"is_private\": false\n  })\n  ```\n- Notes: Content must be plain text.\n\n6) Update a page\u0027s content\n- Purpose: append to or replace the content of an existing page.\n- Sequence:\n  - Confluence_GetPage(page_identifier=\u003cidOrTitle\u003e) to retrieve current content (and confirm correct page)\n  - Confluence_UpdatePageContent(page_identifier=\u003cidOrTitle\u003e, content=\u003cplain text\u003e, update_mode=\"append\"|\"replace\", atlassian_cloud_id=\u003coptional\u003e)\n  - Confluence_GetPage(page_identifier=\u003cidOrTitle\u003e) to verify update\n- Notes: Default update_mode is \"append\". Confirm mode with user.\n\n7) Rename a page\n- Purpose: change page title.\n- Sequence:\n  - Confluence_GetPage(page_identifier=\u003cidOrTitle\u003e) to confirm current title and page ID\n  - Confluence_RenamePage(page_identifier=\u003cidOrTitle\u003e, title=\u003cnewTitle\u003e, atlassian_cloud_id=\u003coptional\u003e)\n  - Confluence_GetPage(page_identifier=\u003cnewTitle\u003e) to verify\n- Notes: Use page ID if the current title is numeric.\n\n8) List attachments workspace-wide or for a page\n- Purpose: discover attachments across workspace or for a specific page.\n- Sequence (workspace):\n  - Confluence_ListAttachments(limit=..., sort_order=..., pagination_token=...)\n- Sequence (page):\n  - Confluence_GetAttachmentsForPage(page_identifier=\u003cidOrTitle\u003e, limit=..., pagination_token=...)\n- Notes: Handle pagination when many attachments exist.\n\n9) Bulk retrieval of many pages (efficient)\n- Purpose: retrieve content for many page IDs in one request.\n- Sequence:\n  - Confluence_GetPagesById(page_ids=[id1, id2, ...], atlassian_cloud_id=\u003coptional\u003e)\n- Notes: Up to 250 page IDs per call. This is preferred over repeated Confluence_GetPage calls.\n\n10) Search then create/update flow (common editing workflow)\n- Purpose: find relevant pages, decide where to edit or create new pages.\n- Sequence:\n  - Confluence_SearchContent(...)\n  - Confluence_GetPagesById(...) for chosen results\n  - Confirm user\u0027s desired edit/create action\n  - Use CreatePage or UpdatePageContent as needed\n  - Verify with Confluence_GetPage\n\n## Examples of ReAct format and tool calls\n\nExample planning step:\n```\nThought: I need to know which cloud the user is on and their identity.\nAction: Confluence_WhoAmI()\nObservation: {user info and list of clouds}\nThought: The user has 2 clouds; I\u0027ll ask which to use or pick the specified cloud_id if provided.\n```\n\nExample search + bulk read:\n```\nThought: Find pages mentioning \"oncall runbook\" and \"pager\" (AND).\nAction: Confluence_SearchContent({\n  \"must_contain_all\": [\"oncall\", \"runbook\"],\n  \"can_contain_any\": [\"pager\", \"alert\"],\n  \"enable_fuzzy\": true,\n  \"limit\": 50\n})\nObservation: {search results with page IDs}\nThought: Fetch full content for the first 10 page IDs.\nAction: Confluence_GetPagesById({\"page_ids\": [123,456,789,...]})\nObservation: {...}\nThought: Summarize key runbook steps and ask user if they want to open or update a page.\n```\n\nExample create page:\n```\nThought: User asked to create a draft design doc in space \u0027ENG\u0027 under parent page 234.\nAction: Confluence_CreatePage({\n  \"space_identifier\": \"ENG\",\n  \"title\": \"New Design Doc (Draft)\",\n  \"content\": \"Draft content...\",\n  \"parent_id\": \"234\",\n  \"is_draft\": true\n})\nObservation: {creation response}\nThought: Confirm creation details with the user and provide link/ID.\n```\n\n## Error handling \u0026 edge cases\n- If a tool call returns an error, report the exact error message and propose next steps (retry with corrected params, ask the user for clarification, or abort).\n- If a title lookup returns an unexpected page (e.g., not the one user meant), confirm identity via page ID or request more details.\n- If returned pagination tokens indicate more results and the user asked for \"all\", iterate until completion (respect limits and warn about time/volume).\n\n## Final guidance for agent behavior\n- Be explicit with each Action call (which tool and the full parameter set).\n- Keep user-facing responses concise and actionable\u2014summaries are preferred; offer to show full content or perform further actions.\n- Ask clarifying questions whenever the user intent is ambiguous (e.g., which space, whether to append or replace content, privacy/draft flags).\n- Respect user privacy: do not expose private pages unless the user explicitly requests access or the `is_private` flag indicates that only the user should see the page.\n\nUse this prompt as the instruction set the ReAct agent follows when interacting with the Confluence toolset.";
// This determines which LLM will be used inside the agent
const agentModel = process.env.OPENAI_MODEL;
if (!agentModel) {
  throw new Error("Missing OPENAI_MODEL. Add it to your .env file.");
}
// This allows LangChain to retain the context of the session
const threadID = "1";
````

Set the following environment variables in a `.env` file:

````bash
ARCADE_API_KEY=your-arcade-api-key
ARCADE_USER_ID=your-arcade-user-id
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-5-mini
````

## Implementing the `tools.ts` module

The `tools.ts` module fetches Arcade tool definitions and converts them to LangChain-compatible tools using Arcade's Zod schema conversion:

### Create the file and import the dependencies

Create a `tools.ts` file, and add import the following. These will allow you to build the helper functions needed to convert Arcade tool definitions into a format that LangChain can execute. Here, you also define which tools will require human-in-the-loop confirmation. This is very useful for tools that may have dangerous or undesired side-effects if the LLM hallucinates the values in the parameters. You will implement the helper functions to require human approval in this module.

````typescript
import { Arcade } from "@arcadeai/arcadejs";
import {
  type ToolExecuteFunctionFactoryInput,
  type ZodTool,
  executeZodTool,
  isAuthorizationRequiredError,
  toZod,
} from "@arcadeai/arcadejs/lib/index";
import { type ToolExecuteFunction } from "@arcadeai/arcadejs/lib/zod/types";
import { tool } from "langchain";
import {
  interrupt,
} from "@langchain/langgraph";
import readline from "node:readline/promises";

// This determines which tools require human in the loop approval to run
const TOOLS_WITH_APPROVAL = ['Confluence_CreatePage', 'Confluence_RenamePage', 'Confluence_UpdatePageContent'];
````

### Create a confirmation helper for human in the loop

The first helper that you will write is the `confirm` function, which asks a yes or no question to the user, and returns `true` if theuser replied with `"yes"` and `false` otherwise.

````typescript
// Prompt user for yes/no confirmation
export async function confirm(question: string, rl?: readline.Interface): Promise<boolean> {
  let shouldClose = false;
  let interface_ = rl;

  if (!interface_) {
      interface_ = readline.createInterface({
          input: process.stdin,
          output: process.stdout,
      });
      shouldClose = true;
  }

  const answer = await interface_.question(`${question} (y/n): `);

  if (shouldClose) {
      interface_.close();
  }

  return ["y", "yes"].includes(answer.trim().toLowerCase());
}
````

Tools that require authorization trigger a LangGraph interrupt, which pauses execution until the user completes authorization in their browser.

### Create the execution helper

This is a wrapper around the `executeZodTool` function. Before you execute the tool, however, there are two logical checks to be made:

1. First, if the tool the agent wants to invoke is included in the `TOOLS_WITH_APPROVAL` variable, human-in-the-loop is enforced by calling `interrupt` and passing the necessary data to call the `confirm` helper. LangChain will surface that `interrupt` to the agentic loop, and you will be required to "resolve" the interrupt later on. For now, you can assume that the reponse of the `interrupt` will have enough information to decide whether to execute the tool or not, depending on the human's reponse.
2. Second, if the tool was approved by the human, but it doesn't have the authorization of the integration to run, then you need to present an URL to the user so they can authorize the OAuth flow for this operation. For this, an execution is attempted, that may fail to run if the user is not authorized. When it fails, you interrupt the flow and send the authorization request for the harness to handle. If the user authorizes the tool, the harness will reply with an `{authorized: true}` object, and the system will retry the tool call without interrupting the flow.

````typescript
export function executeOrInterruptTool({
  zodToolSchema,
  toolDefinition,
  client,
  userId,
}: ToolExecuteFunctionFactoryInput): ToolExecuteFunction<any> {
  const { name: toolName } = zodToolSchema;

  return async (input: unknown) => {
    try {

      // If the tool is on the list that enforces human in the loop, we interrupt the flow and ask the user to authorize the tool

      if (TOOLS_WITH_APPROVAL.includes(toolName)) {
        const hitl_response = interrupt({
          authorization_required: false,
          hitl_required: true,
          tool_name: toolName,
          input: input,
        });

        if (!hitl_response.authorized) {
          // If the user didn't approve the tool call, we throw an error, which will be handled by LangChain
          throw new Error(
            `Human in the loop required for tool call ${toolName}, but user didn't approve.`
          );
        }
      }

      // Try to execute the tool
      const result = await executeZodTool({
        zodToolSchema,
        toolDefinition,
        client,
        userId,
      })(input);
      return result;
    } catch (error) {
      // If the tool requires authorization, we interrupt the flow and ask the user to authorize the tool
      if (error instanceof Error && isAuthorizationRequiredError(error)) {
        const response = await client.tools.authorize({
          tool_name: toolName,
          user_id: userId,
        });

        // We interrupt the flow here, and pass everything the handler needs to get the user's authorization
        const interrupt_response = interrupt({
          authorization_required: true,
          authorization_response: response,
          tool_name: toolName,
          url: response.url ?? "",
        });

        // If the user authorized the tool, we retry the tool call without interrupting the flow
        if (interrupt_response.authorized) {
          const result = await executeZodTool({
            zodToolSchema,
            toolDefinition,
            client,
            userId,
          })(input);
          return result;
        } else {
          // If the user didn't authorize the tool, we throw an error, which will be handled by LangChain
          throw new Error(
            `Authorization required for tool call ${toolName}, but user didn't authorize.`
          );
        }
      }
      throw error;
    }
  };
}
````

### Create the tool retrieval helper

The last helper function of this module is the `getTools` helper. This function will take the configurations you defined in the `main.ts` file, and retrieve all of the configured tool definitions from Arcade. Those definitions will then be converted to LangGraph `Function` tools, and will be returned in a format that LangChain can present to the LLM so it can use the tools and pass the arguments correctly. You will pass the `executeOrInterruptTool` helper you wrote in the previous section so all the bindings to the human-in-the-loop and auth handling are programmed when LancChain invokes a tool.


````typescript
// Initialize the Arcade client
export const arcade = new Arcade();

export type GetToolsProps = {
  arcade: Arcade;
  toolkits?: string[];
  tools?: string[];
  userId: string;
  limit?: number;
}


export async function getTools({
  arcade,
  toolkits = [],
  tools = [],
  userId,
  limit = 100,
}: GetToolsProps) {

  if (toolkits.length === 0 && tools.length === 0) {
      throw new Error("At least one tool or toolkit must be provided");
  }

  // Todo(Mateo): Add pagination support
  const from_toolkits = await Promise.all(toolkits.map(async (tkitName) => {
      const definitions = await arcade.tools.list({
          toolkit: tkitName,
          limit: limit
      });
      return definitions.items;
  }));

  const from_tools = await Promise.all(tools.map(async (toolName) => {
      return await arcade.tools.get(toolName);
  }));

  const all_tools = [...from_toolkits.flat(), ...from_tools];
  const unique_tools = Array.from(
      new Map(all_tools.map(tool => [tool.qualified_name, tool])).values()
  );

  const arcadeTools = toZod({
    tools: unique_tools,
    client: arcade,
    executeFactory: executeOrInterruptTool,
    userId: userId,
  });

  // Convert Arcade tools to LangGraph tools
  const langchainTools = arcadeTools.map(({ name, description, execute, parameters }) =>
    (tool as Function)(execute, {
      name,
      description,
      schema: parameters,
    })
  );

  return langchainTools;
}
````

## Building the Agent

Back on the `main.ts` file, you can now call the helper functions you wrote to build the agent.

### Retrieve the configured tools

Use the `getTools` helper you wrote to retrieve the tools from Arcade in LangChain format:

````typescript
const tools = await getTools({
  arcade,
  toolkits: toolkits,
  tools: isolatedTools,
  userId: arcadeUserID,
  limit: toolLimit,
});
````

### Write an interrupt handler

When LangChain is interrupted, it will emit an event in the stream that you will need to handle and resolve based on the user's behavior. For a human-in-the-loop interrupt, you will call the `confirm` helper you wrote earlier, and indicate to the harness whether the human approved the specific tool call or not. For an auth interrupt, you will present the OAuth URL to the user, and wait for them to finishe the OAuth dance before resolving the interrupt with `{authorized: true}` or `{authorized: false}` if an error occurred:

````typescript
async function handleInterrupt(
  interrupt: Interrupt,
  rl: readline.Interface
): Promise<{ authorized: boolean }> {
  const value = interrupt.value;
  const authorization_required = value.authorization_required;
  const hitl_required = value.hitl_required;
  if (authorization_required) {
    const tool_name = value.tool_name;
    const authorization_response = value.authorization_response;
    console.log("⚙️: Authorization required for tool call", tool_name);
    console.log(
      "⚙️: Please authorize in your browser",
      authorization_response.url
    );
    console.log("⚙️: Waiting for you to complete authorization...");
    try {
      await arcade.auth.waitForCompletion(authorization_response.id);
      console.log("⚙️: Authorization granted. Resuming execution...");
      return { authorized: true };
    } catch (error) {
      console.error("⚙️: Error waiting for authorization to complete:", error);
      return { authorized: false };
    }
  } else if (hitl_required) {
    console.log("⚙️: Human in the loop required for tool call", value.tool_name);
    console.log("⚙️: Please approve the tool call", value.input);
    const approved = await confirm("Do you approve this tool call?", rl);
    return { authorized: approved };
  }
  return { authorized: false };
}
````

### Create an Agent instance

Here you create the agent using the `createAgent` function. You pass the system prompt, the model, the tools, and the checkpointer. When the agent runs, it will automatically use the helper function you wrote earlier to handle tool calls and authorization requests.

````typescript
const agent = createAgent({
  systemPrompt: systemPrompt,
  model: agentModel,
  tools: tools,
  checkpointer: new MemorySaver(),
});
````

### Write the invoke helper

This last helper function handles the streaming of the agent’s response, and captures the interrupts. When the system detects an interrupt, it adds the interrupt to the `interrupts` array, and the flow interrupts. If there are no interrupts, it will just stream the agent’s to your console.

````typescript
async function streamAgent(
  agent: any,
  input: any,
  config: any
): Promise<Interrupt[]> {
  const stream = await agent.stream(input, {
    ...config,
    streamMode: "updates",
  });
  const interrupts: Interrupt[] = [];

  for await (const chunk of stream) {
    if (chunk.__interrupt__) {
      interrupts.push(...(chunk.__interrupt__ as Interrupt[]));
      continue;
    }
    for (const update of Object.values(chunk)) {
      for (const msg of (update as any)?.messages ?? []) {
        console.log("🤖: ", msg.toFormattedString());
      }
    }
  }

  return interrupts;
}
````

### Write the main function

Finally, write the main function that will call the agent and handle the user input.

Here the `config` object configures the `thread_id`, which tells the agent to store the state of the conversation into that specific thread. Like any typical agent loop, you:

1. Capture the user input
2. Stream the agent's response
3. Handle any authorization interrupts
4. Resume the agent after authorization
5. Handle any errors
6. Exit the loop if the user wants to quit

````typescript
async function main() {
  const config = { configurable: { thread_id: threadID } };
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  console.log(chalk.green("Welcome to the chatbot! Type 'exit' to quit."));
  while (true) {
    const input = await rl.question("> ");
    if (input.toLowerCase() === "exit") {
      break;
    }
    rl.pause();

    try {
      let agentInput: any = {
        messages: [{ role: "user", content: input }],
      };

      // Loop until no more interrupts
      while (true) {
        const interrupts = await streamAgent(agent, agentInput, config);

        if (interrupts.length === 0) {
          break; // No more interrupts, we're done
        }

        // Handle all interrupts
        const decisions: any[] = [];
        for (const interrupt of interrupts) {
          decisions.push(await handleInterrupt(interrupt, rl));
        }

        // Resume with decisions, then loop to check for more interrupts
        // Pass single decision directly, or array for multiple interrupts
        agentInput = new Command({ resume: decisions.length === 1 ? decisions[0] : decisions });
      }
    } catch (error) {
      console.error(error);
    }

    rl.resume();
  }
  console.log(chalk.red("👋 Bye..."));
  process.exit(0);
}

// Run the main function
main().catch((err) => console.error(err));
````

## Running the Agent

### Run the agent

```bash
bun run main.ts
```

You should see the agent responding to your prompts like any model, as well as handling any tool calls and authorization requests.

## Next Steps

- Clone the [repository](https://github.com/arcade-agents/ts-langchain-Confluence) and run it
- Add more toolkits to the `toolkits` array to expand capabilities
- Customize the `systemPrompt` to specialize the agent's behavior
- Explore the [Arcade documentation](https://docs.arcade.dev) for available toolkits

