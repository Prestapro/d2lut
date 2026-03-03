import { NextPageContext } from 'next';

interface ErrorProps {
    statusCode: number;
}

function Error({ statusCode }: ErrorProps) {
    return (
        <div style={{
            minHeight: '100vh',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: '#09090b',
            color: '#fff',
            fontFamily: 'system-ui, sans-serif',
        }}>
            <h1 style={{ fontSize: '3rem', fontWeight: 'bold', marginBottom: '1rem' }}>
                {statusCode}
            </h1>
            <p style={{ color: '#71717a' }}>
                {statusCode === 404
                    ? 'This page could not be found.'
                    : 'An error occurred on the server.'}
            </p>
        </div>
    );
}

Error.getInitialProps = ({ res, err }: NextPageContext) => {
    const statusCode = res ? res.statusCode : err ? err.statusCode : 404;
    return { statusCode };
};

export default Error;
