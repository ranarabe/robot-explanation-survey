import { put } from '@vercel/blob';

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed.' });
  }

  try {
    const payload = typeof req.body === 'string' ? JSON.parse(req.body) : (req.body || {});
    const participantId = String(payload.participantId || '').trim();
    const branch = payload.branch;

    if (!participantId || !branch || typeof branch !== 'object') {
      return res.status(400).json({ error: 'Participant ID and branch data are required.' });
    }

    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    const pathname = `alternatives/${participantId}/branch-${stamp}.json`;
    const blob = await put(pathname, JSON.stringify({
      participantId,
      savedAt: new Date().toISOString(),
      branch,
    }, null, 2), {
      access: 'private',
      addRandomSuffix: false,
      allowOverwrite: false,
    });

    return res.status(200).json({ ok: true, pathname: blob.pathname });
  } catch (error) {
    console.error('Alternative branch save failed:', error);
    return res.status(500).json({ error: 'Could not save the alternative branch.' });
  }
}
