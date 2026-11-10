import { put } from '@vercel/blob';

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed.' });
  }

  try {
    const record = typeof req.body === 'string' ? JSON.parse(req.body) : (req.body || {});
    const participantId = String(record.participantId || '').trim();
    if (!participantId) {
      return res.status(400).json({ error: 'Participant ID is required.' });
    }

    const blob = await put(
      `responses/${participantId}.json`,
      JSON.stringify({ ...record, savedAt: new Date().toISOString() }, null, 2),
      { access: 'private', addRandomSuffix: false, allowOverwrite: true }
    );

    return res.status(200).json({ ok: true, pathname: blob.pathname });
  } catch (error) {
    console.error('Could not save participant response:', error);
    return res.status(500).json({ error: 'Could not save the participant response.' });
  }
}
