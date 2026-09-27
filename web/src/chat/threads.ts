import type { AskResponse, Role } from "../api/types";

export type Exchange = {
    id: string;
    question: string;
    steps: string[];
    response: AskResponse | null;
    error: string | null;
};

export type ChatThread = {
    key: string;
    threadId: string | null;
    exchanges: Exchange[];
};

type RoleThreads = { threads: ChatThread[]; activeKey: string };
export type ChatState = Record<Role, RoleThreads>;

export type ChatAction =
    | { type: "newThread"; role: Role; key: string }
    | { type: "selectThread"; role: Role; key: string }
    | { type: "asked"; role: Role; threadKey: string; exchangeId: string; question: string }
    | { type: "step"; role: Role; threadKey: string; exchangeId: string; node: string }
    | { type: "answered"; role: Role; threadKey: string; exchangeId: string; response: AskResponse }
    | { type: "failed"; role: Role; threadKey: string; exchangeId: string; message: string };

let lastKey = 0;
export function nextKey(): string {
    lastKey += 1;
    return `local-${lastKey}`;
}

function emptyThread(key: string): ChatThread {
    return { key, threadId: null, exchanges: [] };
}

function freshRole(): RoleThreads {
    const key = nextKey();
    return { threads: [emptyThread(key)], activeKey: key };
}

export function initialChatState(): ChatState {
    return { support: freshRole(), engineer: freshRole(), admin: freshRole() };
}

export function isStreaming(thread: ChatThread): boolean {
    return thread.exchanges.some((exchange) => !exchange.response && !exchange.error);
}

export function activeThread(roleThreads: RoleThreads): ChatThread {
    const found = roleThreads.threads.find((thread) => thread.key === roleThreads.activeKey);
    if (!found) throw new Error(`active thread ${roleThreads.activeKey} is missing`);
    return found;
}

function withThread(
    state: ChatState,
    role: Role,
    threadKey: string,
    change: (thread: ChatThread) => ChatThread,
): ChatState {
    const threads = state[role].threads.map((thread) =>
        thread.key === threadKey ? change(thread) : thread,
    );
    return { ...state, [role]: { ...state[role], threads } };
}

function withExchange(
    thread: ChatThread,
    exchangeId: string,
    change: (exchange: Exchange) => Exchange,
): ChatThread {
    const exchanges = thread.exchanges.map((exchange) =>
        exchange.id === exchangeId ? change(exchange) : exchange,
    );
    return { ...thread, exchanges };
}

function addThread(state: ChatState, role: Role, key: string): ChatState {
    // Reuse an untouched thread instead of stacking empty ones.
    if (activeThread(state[role]).exchanges.length === 0) return state;
    const threads = [emptyThread(key), ...state[role].threads];
    return { ...state, [role]: { threads, activeKey: key } };
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
    switch (action.type) {
        case "newThread":
            return addThread(state, action.role, action.key);
        case "selectThread":
            return { ...state, [action.role]: { ...state[action.role], activeKey: action.key } };
        case "asked": {
            const exchange: Exchange = {
                id: action.exchangeId,
                question: action.question,
                steps: [],
                response: null,
                error: null,
            };
            return withThread(state, action.role, action.threadKey, (thread) => ({
                ...thread,
                exchanges: [...thread.exchanges, exchange],
            }));
        }
        case "step":
            return withThread(state, action.role, action.threadKey, (thread) =>
                withExchange(thread, action.exchangeId, (ex) => ({
                    ...ex,
                    steps: [...ex.steps, action.node],
                })),
            );
        case "answered":
            return withThread(state, action.role, action.threadKey, (thread) => ({
                ...withExchange(thread, action.exchangeId, (ex) => ({
                    ...ex,
                    response: action.response,
                })),
                threadId: action.response.thread_id,
            }));
        case "failed":
            return withThread(state, action.role, action.threadKey, (thread) =>
                withExchange(thread, action.exchangeId, (ex) => ({ ...ex, error: action.message })),
            );
    }
}
