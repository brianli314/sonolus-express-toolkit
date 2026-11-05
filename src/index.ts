import express from 'express'
import { Sonolus } from '@sonolus/express'

declare module '@sonolus/express' {
    interface LevelItemModel {
        meta: {
            addedAt: number
        }
    }
    interface PlaylistItemModel {
        meta: {
            addedAt: number
        }
    }
}

const SECTION_SIZE = 5

function getNewestItems<T>(items: T[], size = SECTION_SIZE): T[] {
    return items.slice(0, size)
}

function getRandomItems<T>(items: T[], size = SECTION_SIZE): T[] {
    const shuffled = [...items]
    for (let i = shuffled.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1))
        ;[shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]]
    }
    return shuffled.slice(0, size)
}

const port = 3000

const sonolus = new Sonolus({address: 'https://sonolus.bli-mc.tzhou.net'})

sonolus.level.infoHandler = () => ({
    searches: {},
    sections: [
        { title: { en: 'Random' }, itemType: 'level', items: getRandomItems(sonolus.level.items) },
        { title: { en: 'Newest' }, itemType: 'level', items: getNewestItems(sonolus.level.items) },
    ],
})

sonolus.playlist.infoHandler = () => ({
    searches: {},
    sections: [
        { title: { en: 'Random' }, itemType: 'playlist', items: getRandomItems(sonolus.playlist.items) },
        { title: { en: 'Newest' }, itemType: 'playlist', items: getNewestItems(sonolus.playlist.items) },

    ],
})

sonolus.load('./pack')

sonolus.level.items.sort((a, b) => b.meta.addedAt - a.meta.addedAt)
sonolus.playlist.items.sort((a, b) => b.meta.addedAt - a.meta.addedAt)

const app = express()

app.get('/health', (_req, res) => {
    res.json({ status: 'ok' })
})

app.get('/all.scp', (req, res) => res.download('all.scp'))

app.use(sonolus.router)

app.listen(port, () => {
    console.log(`Sonolus server listening on port ${port}`)
})