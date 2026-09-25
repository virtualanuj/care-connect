import { Link } from 'react-router-dom'

export default function ForbiddenPage() {
  return (
    <section>
      <h1>Not permitted</h1>
      <p>You do not have permission to view this page.</p>
      <Link to="/">Back to home</Link>
    </section>
  )
}
