import express from 'express'
import { Sonolus } from '@sonolus/express'

const port = Number(process.env.PORT ?? 3000)

const sonolus = new Sonolus()
sonolus.load('./pack')

const app = express()

app.get('/health', (_req, res) => {
    res.json({ status: 'ok' })
})

app.use(sonolus.router)

app.listen(port, '0.0.0.0', () => {
    console.log(`Sonolus server listening on port ${port}`)
})