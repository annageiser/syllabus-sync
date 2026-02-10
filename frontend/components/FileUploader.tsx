import React, { useCallback } from 'react';

interface FileUploaderProps {
    onFileUpload: (file: File) => void;
}

const FileUploader: React.FC<FileUploaderProps> = ({ onFileUpload }) => {
    const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            onFileUpload(e.dataTransfer.files[0]);
        }
    }, [onFileUpload]);

    const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
    }, []);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            onFileUpload(e.target.files[0]);
        }
    };

    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLDivElement>) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            document.getElementById('file-upload')?.click();
        }
    }, []);

    return (
        <div
            className="border-2 border-dashed border-gray-300 rounded-lg p-10 text-center hover:bg-gray-50 transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onKeyDown={handleKeyDown}
            tabIndex={0}
            role="button"
            aria-label="Upload syllabus file (Double-click or press Enter to browse files)"
        >
            <input
                type="file"
                className="hidden"
                id="file-upload"
                onChange={handleChange}
                accept=".pdf,.xlsx,.xls,.docx,.html,.htm"
            />
            <label htmlFor="file-upload" className="cursor-pointer block">
                <div className="text-4xl mb-4" aria-hidden="true">📄</div>
                <h3 className="text-lg font-semibold mb-2">Drag & Drop your schedule here</h3>
                <p className="text-gray-500 text-sm">Supports PDF, Excel, Word, HTML</p>
                <div className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition inline-block">
                    Browse Files
                </div>
            </label>
        </div>
    );
};

export default FileUploader;
