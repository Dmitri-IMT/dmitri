import { existsSync, readFileSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

function projectDirectories(cwd: string): string[] {
	const directories: string[] = [];
	let current = resolve(cwd);

	while (true) {
		directories.unshift(current);
		if (existsSync(join(current, ".git"))) break;

		const parent = dirname(current);
		if (parent === current) break;
		current = parent;
	}

	return directories;
}

function existingDirectories(paths: string[]): string[] {
	return [...new Set(paths)].filter((path) => existsSync(path) && statSync(path).isDirectory());
}

function existingFiles(paths: string[]): string[] {
	return [...new Set(paths)].filter((path) => existsSync(path) && statSync(path).isFile());
}

export default function agentCompat(pi: ExtensionAPI) {
	let claudeContextFiles: Array<{ path: string; content: string }> = [];

	pi.on("session_start", (_event, ctx) => {
		const directories = projectDirectories(ctx.cwd);
		claudeContextFiles = existingFiles([
			join(homedir(), ".claude", "CLAUDE.md"),
			...directories.flatMap((directory) => [
				join(directory, "CLAUDE.md"),
				join(directory, ".claude", "CLAUDE.md"),
			]),
		]).map((path) => ({ path, content: readFileSync(path, "utf8") }));
	});

	pi.on("resources_discover", (event) => {
		const directories = projectDirectories(event.cwd);
		return {
			skillPaths: existingDirectories([
				join(homedir(), ".agents", "skills"),
				join(homedir(), ".claude", "skills"),
				...directories.flatMap((directory) => [
					join(directory, ".agents", "skills"),
					join(directory, ".claude", "skills"),
				]),
			]),
		};
	});

	pi.on("before_agent_start", (event) => {
		const loadedPaths = new Set(
			event.systemPromptOptions.contextFiles?.map((file) => resolve(file.path)) ?? [],
		);
		const additionalContext = claudeContextFiles.filter(
			(file) => !loadedPaths.has(resolve(file.path)),
		);
		if (additionalContext.length === 0) return;

		const context = additionalContext
			.map(
				(file) =>
					`<project_instructions path="${file.path}">\n${file.content}\n</project_instructions>`,
			)
			.join("\n\n");

		return {
			systemPrompt: `${event.systemPrompt}\n\n<project_context>\n\nProject-specific instructions and guidelines:\n\n${context}\n\n</project_context>`,
		};
	});
}
