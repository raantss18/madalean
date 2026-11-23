// Session S-AZ endpoints (docs/API.md « MCP », docs/MCP.md): Madalean as an MCP server, external MCP servers.
// Every route is host-only. Kept apart from client.ts so the parallel sessions do not edit the same file.
import { request } from './client';

export interface McpToolInfo {
  name: string; title: string; description: string; available: boolean; rate: number;
  inputSchema: Record<string, unknown>;
}
export interface McpConnect {
  command: string; args: string[]; shell: string; claude_code: string; json: Record<string, unknown>;
  http_url: string; claude_code_http: string;
}
export interface McpExternalTool { name: string; title: string; description: string; safe: boolean }
export interface McpExternal {
  id: string; name: string; transport: 'stdio' | 'http'; command: string[]; url: string; enabled: boolean;
  allowed: string[]; tools: McpExternalTool[]; timeout_s: number;
  status: { ok?: boolean; t?: number; error?: string; name?: string; version?: string; tools?: number; stderr?: string[] };
}
export interface McpInfo {
  server: { enabled: boolean; http: boolean; sage: boolean; tools: McpToolInfo[]; protocol: string; connect: McpConnect };
  servers: McpExternal[];
  max_timeout: number;
}
export interface McpActivity {
  t: number; dir: 'in' | 'out'; transport: string; server: string; tool: string; ok: boolean; ms: number; error: string;
}

export const mcp = {
  info: () => request<McpInfo>('GET', '/mcp'),
  activity: () => request<{ activity: McpActivity[] }>('GET', '/mcp/activity'),
  add: (b: { name: string; transport: 'stdio' | 'http'; command?: string; url?: string }) =>
    request<{ server: McpExternal }>('POST', '/mcp/servers', b),
  patch: (id: string, b: Partial<Pick<McpExternal, 'name' | 'enabled' | 'allowed' | 'timeout_s'>>) =>
    request<{ server: McpExternal }>('PATCH', `/mcp/servers/${encodeURIComponent(id)}`, b),
  remove: (id: string) => request<{ removed: string }>('DELETE', `/mcp/servers/${encodeURIComponent(id)}`),
  test: (id: string) => request<{ server: McpExternal }>('POST', `/mcp/servers/${encodeURIComponent(id)}/test`),
};
