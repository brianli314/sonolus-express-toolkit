import express from 'express'
import { Sonolus } from '@sonolus/express'

const port = 3000

const sonolus = new Sonolus()

sonolus.level.infoHandler = () => {
    const allItems = sonolus.level.items
    const sectionSize = 5 // however many items you want per row

    const newestItems = allItems.slice(0, sectionSize)

    const randomItems = [...allItems]
    for (let i = randomItems.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1))
        ;[randomItems[i], randomItems[j]] = [randomItems[j], randomItems[i]]
    }
    const randomSection = randomItems.slice(0, sectionSize)

    return {
        searches: {},
        sections: [
            {
                title: { en: 'Newest' },
                itemType: 'level',
                items: newestItems,
            },
            {
                title: { en: 'Random' },
                itemType: 'level',
                items: randomSection,
            },
        ],
    }
}

sonolus.load('./pack')

const app = express()

app.get('/health', (_req, res) => {
    res.json({ status: 'ok' })
})

app.use(sonolus.router)

app.listen(port, () => {
    console.log(`Sonolus server listening on port ${port}`)
})