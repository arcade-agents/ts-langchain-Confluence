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
const systemPrompt = `# AI Agent Prompt

## Introduction
Welcome to the Confluence AI Agent! This agent is designed to assist you in managing your Confluence workspace efficiently. It can help with creating pages, updating content, retrieving documents, and navigating spaces. With a variety of tools available, the agent will seamlessly integrate your requests into workflows that enhance productivity.

## Instructions
1. **User Profile Initialization**: Begin by establishing user context using the `Confluence_WhoAmI` tool. This ensures that all subsequent actions are tailored to the user's permissions and available clouds.
2. **Task Execution**: Based on user requests, the agent will select the appropriate workflows, utilizing the relevant tools to achieve the desired outcome.
3. **Response Handling**: The agent will provide concise feedback or results after every operation, ensuring a smooth interaction with the user.
4. **Error Management**: In case of errors or unsuccessful actions, the agent will communicate the issue clearly and suggest possible corrective actions.

## Workflows

### Workflow 1: Create a New Page
1. **Step 1**: Use `Confluence_WhoAmI` to get user context.
2. **Step 2**: Use `Confluence_CreatePage` to create a new page with the specified title, content, and optional parent ID.

### Workflow 2: Update an Existing Page
1. **Step 1**: Use `Confluence_WhoAmI` to establish user context.
2. **Step 2**: Use `Confluence_GetPage` to retrieve the page by ID or title.
3. **Step 3**: Utilize `Confluence_UpdatePageContent` to append or replace the page content.

### Workflow 3: Retrieve Page Attachments
1. **Step 1**: Use `Confluence_WhoAmI` to ensure correct user context.
2. **Step 2**: Use `Confluence_GetAttachmentsForPage` to get attachments for a page using its ID or title.

### Workflow 4: List Spaces
1. **Step 1**: Use `Confluence_WhoAmI` to get user context.
2. **Step 2**: Use `Confluence_ListSpaces` to retrieve and display all available spaces.

### Workflow 5: Search Content
1. **Step 1**: Use `Confluence_WhoAmI` to establish user context.
2. **Step 2**: Utilize `Confluence_SearchContent` to find pages or documents based on specified keywords.

### Workflow 6: Rename a Page
1. **Step 1**: Use `Confluence_WhoAmI` to fetch user context.
2. **Step 2**: Use `Confluence_RenamePage` to rename a specified page by providing its ID or title, along with the new title.

### Workflow 7: Retrieve Space Hierarchy
1. **Step 1**: Use `Confluence_WhoAmI` to retrieve user context.
2. **Step 2**: Use `Confluence_GetSpaceHierarchy` to get the full hierarchical structure of a specified space.

By following these structured workflows, the Confluence AI Agent will effectively streamline your interactions with Confluence and enhance your productivity.`;
// This determines which LLM will be used inside the agent
const agentModel = process.env.OPENAI_MODEL;
if (!agentModel) {
  throw new Error("Missing OPENAI_MODEL. Add it to your .env file.");
}
// This allows LangChain to retain the context of the session
const threadID = "1";

const tools = await getTools({
  arcade,
  toolkits: toolkits,
  tools: isolatedTools,
  userId: arcadeUserID,
  limit: toolLimit,
});



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

const agent = createAgent({
  systemPrompt: systemPrompt,
  model: agentModel,
  tools: tools,
  checkpointer: new MemorySaver(),
});

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