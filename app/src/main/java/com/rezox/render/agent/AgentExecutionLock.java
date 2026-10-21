package com.rezox.render.agent;

import java.util.concurrent.atomic.AtomicBoolean;

/** One native scene mutation/inspection lane, across relay and local VideoStudio IPC. */
final class AgentExecutionLock {
    static final AtomicBoolean BUSY = new AtomicBoolean(false);
    private AgentExecutionLock() {}
}
