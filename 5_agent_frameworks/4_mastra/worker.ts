/**
 * The Mastra worker: the terminal version of step 5, plus the bits the Day 5 project
 * needs.
 *
 * Run bare (npm run worker), it seeds and works its own goal (read notes.txt,
 * translate to Hindi, write hindi.txt): plan the steps on the board, read the
 * file through the filesystem MCP server, translate, write the Hindi back, and tick
 * each step off before closing the goal. The onStepFinish callback prints each tool
 * call as it happens, so you can watch the loop turn.
 *
 * Given a task id and a shared board path, the same worker joins the Day 5 agent loop
 * instead: it points its file tools at the shared site, claims that one task, builds
 * what the task asks, and exits, leaving the rest of the board alone. The board path
 * arrives through the BOARD_PATH environment variable (board.ts reads it at import,
 * before this module runs) and the model through WORKER_MODEL, both set by the
 * orchestrator; a hand run can pass them the same way:
 *
 *   npm run worker                                             # standalone demo
 *   BOARD_PATH=<path> npx tsx worker.ts <taskId> <boardPath>   # Day 5: one shared task
 */

import "./env.ts";
import { join, dirname } from "node:path";
import { mkdirSync, rmSync, existsSync, readFileSync } from "node:fs";
import { Agent } from "@mastra/core/agent";
import { boardTools, makeFilesystem, Workspace } from "./tools.ts";
import { ResetBoard, AddGoal, ClaimTodo, ShowBoard, BoardPath } from "./board.ts";

// Day 5 mode is "<taskId> <boardPath>". Run bare (npm run worker), none of this fires.
const args = process.argv.slice(2);
const TaskId = args.length >= 2 ? Number(args[0]) : null;
// File tools write into this worker's own workspace when standalone, or the shared
// site (the board file's folder) when working a Day 5 task.
const WorkDir = TaskId === null ? Workspace : dirname(BoardPath);

const Goal = "Read notes.txt, translate its contents into natural Hindi, and write the Hindi to hindi.txt.";

const INSTRUCTIONS = `
You are a careful worker with a shared todo board and a set of file tools.

Take the pending goal and see it through. Begin by laying out a short plan: the handful of concrete steps the work itself breaks down into, added to the board under the goal. Then carry them out with your file tools, marking each step done as you finish it. Once the steps are all done, close the goal. Your files live in the single folder your tools are allowed to use.
`;

/** Reset the board, clear any old output, and add the one goal. */
function seed(): number {
  mkdirSync(Workspace, { recursive: true });
  rmSync(join(Workspace, "hindi.txt"), { force: true });
  ResetBoard();
  const GoalId = AddGoal(Goal);
  ClaimTodo(GoalId); // the worker picks up the goal: pending -> in_progress
  return GoalId;
}

let Message: string;
if (TaskId === null) {
  const GoalId = seed();
  console.log(`Seeded goal ${GoalId}: ${Goal}\n`);
  Message = "Please work the pending goal on the board.";
} else {
  ClaimTodo(TaskId); // light up this one task on the shared board
  Message =
    `You have claimed task #${TaskId} on the shared board. Work only that task and its steps. ` +
    `When the work is built and checked, mark task #${TaskId} itself done with CompleteTask, then stop.`;
}

const Filesystem = makeFilesystem(WorkDir);
const Worker = new Agent({
  id: "worker",
  name: "Worker",
  instructions: INSTRUCTIONS,
  model: "openai/" + (process.env.WORKER_MODEL ?? "gpt-5.4-mini"),
  tools: { ...boardTools, ...(await Filesystem.listTools()) },
});

await Worker.generate(Message, {
  maxSteps: 25,
  onStepFinish: (step: { toolCalls?: { payload: { toolName: string; args?: unknown } }[] }) => {
    if (TaskId !== null) return; // on Day 5 the orchestrator owns the console
    for (const call of step.toolCalls ?? []) {
      console.log(`  called ${call.payload.toolName}(${JSON.stringify(call.payload.args)})`);
    }
  },
});
await Filesystem.disconnect();

if (TaskId === null) {
  // standalone: show the result; on Day 5 the orchestrator renders the shared board
  console.log("\nBoard after the run:");
  ShowBoard();
  const Hindi = join(Workspace, "hindi.txt");
  if (existsSync(Hindi)) {
    console.log("\nhindi.txt:\n" + readFileSync(Hindi, "utf-8"));
  }
}

process.exit(0); // Mastra keeps its model connection pool open, so exit once the work is done
