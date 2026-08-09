import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { ToolExecutionComponent } from "@earendil-works/pi-coding-agent";

const TOOL_RENDER_PATCH = Symbol.for("dmitri.pi.chill.tool-render");

type ToolRender = (this: ToolExecutionComponent, width: number) => string[];

interface ToolRenderPatchState {
	enabled: boolean;
	originalRender: ToolRender;
}

/**
 * Pi uses one component for every built-in and extension tool row. The public
 * extension API has no global tool-visibility setting, so keep this patch
 * isolated, idempotent, and display-only.
 */
function installToolRenderPatch(): ToolRenderPatchState {
	const prototype = ToolExecutionComponent.prototype as unknown as Record<PropertyKey, unknown>;
	let state = prototype[TOOL_RENDER_PATCH] as ToolRenderPatchState | undefined;
	if (state) return state;

	state = {
		enabled: false,
		originalRender: ToolExecutionComponent.prototype.render,
	};
	Object.defineProperty(prototype, TOOL_RENDER_PATCH, { value: state });

	const patchState = state;
	ToolExecutionComponent.prototype.render = function (this: ToolExecutionComponent, width: number) {
		return patchState.enabled ? [] : patchState.originalRender.call(this, width);
	};

	return state;
}

export default function chillExtension(pi: ExtensionAPI) {
	let chillEnabled = false;
	const toolRenderPatch = installToolRenderPatch();

	const applyUi = (ctx: ExtensionContext) => {
		toolRenderPatch.enabled = chillEnabled;
		ctx.ui.setWorkingVisible(true);
		ctx.ui.setWorkingMessage(chillEnabled ? "Working..." : undefined);
		ctx.ui.setStatus("chill", chillEnabled ? "☕ chill" : undefined);
	};

	// Thinking content is display-only here; it remains in the session and context.
	pi.registerMarkdownTransformer((markdown, { messageType }) => {
		if (chillEnabled && messageType === "assistant-thinking") return "";
		return markdown;
	});

	// Avoid leaving the process-wide renderer hidden after /reload or /new.
	pi.on("session_shutdown", () => {
		toolRenderPatch.enabled = false;
	});

	pi.registerCommand("chill", {
		description: "Toggle quiet TUI mode for thinking and tool output",
		handler: async (args, ctx) => {
			const requested = args.trim().toLowerCase();
			if (requested && requested !== "on" && requested !== "off") {
				ctx.ui.notify("Usage: /chill [on|off]", "error");
				return;
			}

			chillEnabled = requested ? requested === "on" : !chillEnabled;
			applyUi(ctx);
			ctx.ui.notify(chillEnabled ? "Chill mode on ☕" : "Chill mode off", "info");
		},
	});
}
