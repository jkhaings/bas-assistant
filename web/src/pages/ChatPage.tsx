import type { Dispatch } from "react";
import { askStream } from "../api/askStream";
import { useApi } from "../api/context";
import type { Role } from "../api/types";
import {
    activeThread,
    isStreaming,
    type ChatAction,
    type ChatState,
    type ChatThread,
} from "../chat/threads";
import { Composer } from "../components/chat/Composer";
import { ExchangeView } from "../components/chat/ExchangeView";
import { StarterQuestions } from "../components/chat/StarterQuestions";
import { ThreadList } from "../components/chat/ThreadList";

type ConversationProps = { thread: ChatThread; busy: boolean; onAsk: (question: string) => void };

function Conversation({ thread, busy, onAsk }: ConversationProps) {
    return (
        <section aria-label="Conversation" className="min-w-0 space-y-6">
            {thread.exchanges.length === 0 ? (
                <StarterQuestions busy={busy} onPick={onAsk} />
            ) : (
                thread.exchanges.map((exchange) => (
                    <ExchangeView key={exchange.id} exchange={exchange} />
                ))
            )}
            <Composer busy={busy} onAsk={onAsk} />
        </section>
    );
}

type Props = {
    role: Role;
    chat: ChatState;
    dispatch: Dispatch<ChatAction>;
    onAskFinished: () => void;
};

export function ChatPage({ role, chat, dispatch, onAskFinished }: Props) {
    const client = useApi();
    const roleThreads = chat[role];
    const thread = activeThread(roleThreads);
    const busy = isStreaming(thread);

    async function ask(question: string) {
        const target = { role, threadKey: thread.key, exchangeId: crypto.randomUUID() };
        dispatch({ type: "asked", ...target, question });
        const outcome = await askStream(client, { question, thread_id: thread.threadId }, (node) =>
            dispatch({ type: "step", ...target, node }),
        );
        if (outcome.kind === "answer") {
            dispatch({ type: "answered", ...target, response: outcome.response });
        } else {
            dispatch({ type: "failed", ...target, message: outcome.message });
        }
        onAskFinished();
    }

    return (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-[15rem_minmax(0,1fr)]">
            <ThreadList
                threads={roleThreads.threads}
                activeKey={roleThreads.activeKey}
                onSelect={(key) => dispatch({ type: "selectThread", role, key })}
                onNew={() => dispatch({ type: "newThread", role, key: crypto.randomUUID() })}
            />
            <Conversation thread={thread} busy={busy} onAsk={(question) => void ask(question)} />
        </div>
    );
}
