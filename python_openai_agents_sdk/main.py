from agents import (Agent, Runner, AgentHooks, Tool, RunContextWrapper,
                    TResponseInputItem,)
from functools import partial
from arcadepy import AsyncArcade
from agents_arcade import get_arcade_tools
from typing import Any
from human_in_the_loop import (UserDeniedToolCall,
                               confirm_tool_usage,
                               auth_tool)

import globals


class CustomAgentHooks(AgentHooks):
    def __init__(self, display_name: str):
        self.event_counter = 0
        self.display_name = display_name

    async def on_start(self,
                       context: RunContextWrapper,
                       agent: Agent) -> None:
        self.event_counter += 1
        print(f"### ({self.display_name}) {
              self.event_counter}: Agent {agent.name} started")

    async def on_end(self,
                     context: RunContextWrapper,
                     agent: Agent,
                     output: Any) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {
                # agent.name} ended with output {output}"
                agent.name} ended"
        )

    async def on_handoff(self,
                         context: RunContextWrapper,
                         agent: Agent,
                         source: Agent) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {
                source.name} handed off to {agent.name}"
        )

    async def on_tool_start(self,
                            context: RunContextWrapper,
                            agent: Agent,
                            tool: Tool) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}:"
            f" Agent {agent.name} started tool {tool.name}"
            f" with context: {context.context}"
        )

    async def on_tool_end(self,
                          context: RunContextWrapper,
                          agent: Agent,
                          tool: Tool,
                          result: str) -> None:
        self.event_counter += 1
        print(
            f"### ({self.display_name}) {self.event_counter}: Agent {
                # agent.name} ended tool {tool.name} with result {result}"
                agent.name} ended tool {tool.name}"
        )


async def main():

    context = {
        "user_id": os.getenv("ARCADE_USER_ID"),
    }

    client = AsyncArcade()

    arcade_tools = await get_arcade_tools(
        client, toolkits=["Confluence"]
    )

    for tool in arcade_tools:
        # - human in the loop
        if tool.name in ENFORCE_HUMAN_CONFIRMATION:
            tool.on_invoke_tool = partial(
                confirm_tool_usage,
                tool_name=tool.name,
                callback=tool.on_invoke_tool,
            )
        # - auth
        await auth_tool(client, tool.name, user_id=context["user_id"])

    agent = Agent(
        name="",
        instructions="# AI Agent Prompt

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

By following these structured workflows, the Confluence AI Agent will effectively streamline your interactions with Confluence and enhance your productivity.",
        model=os.environ["OPENAI_MODEL"],
        tools=arcade_tools,
        hooks=CustomAgentHooks(display_name="")
    )

    # initialize the conversation
    history: list[TResponseInputItem] = []
    # run the loop!
    while True:
        prompt = input("You: ")
        if prompt.lower() == "exit":
            break
        history.append({"role": "user", "content": prompt})
        try:
            result = await Runner.run(
                starting_agent=agent,
                input=history,
                context=context
            )
            history = result.to_input_list()
            print(result.final_output)
        except UserDeniedToolCall as e:
            history.extend([
                {"role": "assistant",
                 "content": f"Please confirm the call to {e.tool_name}"},
                {"role": "user",
                 "content": "I changed my mind, please don't do it!"},
                {"role": "assistant",
                 "content": f"Sure, I cancelled the call to {e.tool_name}."
                 " What else can I do for you today?"
                 },
            ])
            print(history[-1]["content"])

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())