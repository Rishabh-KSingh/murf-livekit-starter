import { NextResponse } from 'next/server';
import fs from 'node:fs';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';

export const dynamic = 'force-dynamic';
export const revalidate = 0;
export const runtime = 'nodejs';

function resolveDbPath(): string {
  if (process.env.DATABASE_PATH && fs.existsSync(process.env.DATABASE_PATH)) {
    return process.env.DATABASE_PATH;
  }

  const candidates = [
    path.resolve(process.cwd(), '..', 'backend', 'kisan_mitra.db'),
    path.resolve(process.cwd(), 'backend', 'kisan_mitra.db'),
    path.resolve(process.cwd(), 'kisan_mitra.db'),
    path.resolve(__dirname, '..', '..', '..', '..', 'backend', 'kisan_mitra.db'),
    path.resolve(__dirname, '..', '..', '..', 'backend', 'kisan_mitra.db'),
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  return candidates[0];
}

export async function GET() {
  try {
    const dbPath = resolveDbPath();

    // Open SQLite database
    const db = new DatabaseSync(dbPath);

    // Ensure call_logs table exists if database is new
    db.exec(`
      CREATE TABLE IF NOT EXISTS call_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'failed',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Query aggregated call analytics
    const stmt = db.prepare(`
      SELECT
        COUNT(*) as total_calls,
        COALESCE(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END), 0) as successful_calls,
        COALESCE(SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END), 0) as failed_calls
      FROM call_logs
    `);

    const row = stmt.get() as
      | {
          total_calls: number | bigint;
          successful_calls: number | bigint;
          failed_calls: number | bigint;
        }
      | undefined;

    const total = Number(row?.total_calls ?? 0);
    const successful = Number(row?.successful_calls ?? 0);
    const failed = Number(row?.failed_calls ?? 0);

    // Query recent call logs (last 10 calls)
    let recentLogs: Array<{
      id: number;
      session_id: string;
      status: string;
      created_at: string;
    }> = [];

    try {
      const logsStmt = db.prepare(`
        SELECT id, session_id, status, created_at
        FROM call_logs
        ORDER BY id DESC
        LIMIT 10
      `);
      const logs = logsStmt.all() as Array<{
        id: number | bigint;
        session_id: string;
        status: string;
        created_at: string;
      }>;
      recentLogs = logs.map((l) => ({
        id: Number(l.id),
        session_id: String(l.session_id || ''),
        status: String(l.status || 'failed'),
        created_at: String(l.created_at || ''),
      }));
    } catch (e) {
      console.warn('Could not fetch recent call logs:', e);
    }

    db.close();

    return NextResponse.json(
      {
        total_calls: total,
        successful_calls: successful,
        failed_calls: failed,
        recent_logs: recentLogs,
      },
      {
        headers: {
          'Cache-Control': 'no-store, no-cache, must-revalidate, proxy-revalidate',
        },
      }
    );
  } catch (error) {
    console.error('Failed to fetch call analytics from SQLite:', error);
    return NextResponse.json(
      {
        total_calls: 0,
        successful_calls: 0,
        failed_calls: 0,
        recent_logs: [],
        error: error instanceof Error ? error.message : 'Database error',
      },
      { status: 500 }
    );
  }
}
