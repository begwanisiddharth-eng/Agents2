/**
 * The tools we give the agent: three small board tools and the filesystem MCP
 * server. These are the same three operations every framework gets this week,
 * here written the Mastra way with createTool and zod schemas. The step files
 * and the worker all import them from here, so the agent is given the same tools
 * everywhere.
 */

import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createTool } from "@mastra/core/tools";
import { MCPClient } from "@mastra/mcp";
import { z } from "zod";
import { AddStep, ListTodos, CompleteTodo } from "./board.ts";

/** The one folder the filesystem server is allowed to touch. */
export const Workspace = join(dirname(fileURLToPath(import.meta.url)), "workspace");

export const ShowTodos = createTool({
  id: "ShowTodos",
  description: "List every todo on the board. A goal has parent_id null; a step has parent_id set to its goal's id.",
  inputSchema: z.object({}),
  execute: async () => ({ todos: ListTodos() }),
});

export const PlanSteps = createTool({
  id: "PlanSteps",
  description: "Break a goal into an ordered checklist of steps on the board. Pass the goal's id and a short list of step descriptions.",
  inputSchema: z.object({ goalId: z.number(), steps: z.array(z.string()) }),
  execute: async ({ goalId, steps }) => ({ goalId, stepIds: steps.map((s: string) => AddStep(goalId, s)) }),
});

export const CompleteTask = createTool({
  id: "CompleteTask",
  description: "Mark a todo (a step or the goal) with this id as done and record a short result summary.",
  inputSchema: z.object({ taskId: z.number(), result: z.string() }),
  execute: async ({ taskId, result }) => {
    CompleteTodo(taskId, result);
    return { taskId, status: "done" };
  },
});

/** Attach to an agent with tools: { ...boardTools }. */
export const boardTools = { ShowTodos, PlanSteps, CompleteTask };

/**
 * The filesystem reference server, the same Node server every framework uses
 * this week, scoped to a single folder. Mastra exposes both fixes the day needs
 * as plain options on the stdio server: stderr "ignore" discards the server's
 * startup banner and lets it run from a Jupyter kernel on Windows, and cwd starts
 * the server in the workspace so the agent's relative file names resolve there.
 * No subclass and no monkeypatch, which makes this the cleanest MCP wiring of the
 * week. Open it with await mcp.listTools() and close it with await mcp.disconnect().
 */
export function makeFilesystem(dir = Workspace): MCPClient {
  return new MCPClient({
    servers: {
      Filesystem: {
        command: "npx",
        args: ["-y", "@modelcontextprotocol/server-filesystem", dir],
        stderr: "ignore",
        cwd: dir,
      },
    },
  });
}
